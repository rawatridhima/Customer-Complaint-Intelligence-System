"""Fine-tune DistilBERT on the same splits as the baseline.

Usage (from ml/src):
    # quick local smoke test, a few minutes on a laptop
    python train_transformer.py --data-dir ../data --limit 300 --epochs 1

    # real run on Colab GPU
    python train_transformer.py --data-dir <path> --max-length 256
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

from label_mapping import CATEGORIES, MAPPING_VERSION
from preprocess import normalise

BASE_MODEL = "distilbert-base-uncased"


class WeightedTrainer(Trainer):
    """Trainer with class-weighted cross-entropy (DR-04)."""

    def __init__(self, *args, class_weights: torch.Tensor, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss = torch.nn.functional.cross_entropy(
            outputs.logits, labels, weight=self.class_weights.to(outputs.logits.device)
        )
        return (loss, outputs) if return_outputs else loss


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("../models/distilbert-v1"))
    p.add_argument("--max-length", type=int, default=256)
    p.add_argument("--epochs", type=int, default=4)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=0, help="rows per split, for smoke tests")
    args = p.parse_args()

    splits = {s: pd.read_csv(args.data_dir / f"{s}.csv") for s in ("train", "val", "test")}
    if args.limit:
        splits = {s: df.sample(min(len(df), args.limit), random_state=args.seed)
                  for s, df in splits.items()}

    label2id = {label: i for i, label in enumerate(CATEGORIES)}
    tok = AutoTokenizer.from_pretrained(BASE_MODEL)

    def to_dataset(df: pd.DataFrame) -> Dataset:
        ds = Dataset.from_dict({
            "text": df["text"].map(normalise).tolist(),
            "label": df["label"].map(label2id).tolist(),
        })
        return ds.map(lambda b: tok(b["text"], truncation=True, max_length=args.max_length),
                      batched=True, remove_columns=["text"])

    train_ds, val_ds, test_ds = (to_dataset(splits[s]) for s in ("train", "val", "test"))

    counts = splits["train"]["label"].value_counts().reindex(CATEGORIES).fillna(1).values
    weights = torch.tensor(len(splits["train"]) / (len(CATEGORIES) * counts), dtype=torch.float)

    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=len(CATEGORIES),
        id2label={i: l for l, i in label2id.items()}, label2id=label2id,
    )

    def compute_metrics(pred):
        return {"macro_f1": f1_score(pred.label_ids, pred.predictions.argmax(-1), average="macro")}

    steps_per_epoch = -(-len(train_ds) // args.batch_size)   # ceiling division
    warmup_steps = int(0.1 * steps_per_epoch * args.epochs)  # 10% warmup, as in the LLD
    training_args = TrainingArguments(
        output_dir=str(args.out / "checkpoints"),
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        num_train_epochs=args.epochs,
        warmup_steps=warmup_steps,
        weight_decay=0.01,
        seed=args.seed,
        fp16=torch.cuda.is_available(),
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        save_total_limit=1,
        logging_steps=50,
        report_to="none",
    )

    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tok,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
        class_weights=weights,
    )
    trainer.train()

    val_f1 = trainer.evaluate(val_ds)["eval_macro_f1"]
    preds = trainer.predict(test_ds)
    y_true, y_pred = preds.label_ids, preds.predictions.argmax(-1)
    test_f1 = f1_score(y_true, y_pred, average="macro")

    print("\n=== Test set ===")
    print(classification_report(y_true, y_pred, labels=range(len(CATEGORIES)),
                                target_names=CATEGORIES, digits=3, zero_division=0))
    print("Confusion matrix (rows = true, columns = predicted):")
    print(pd.DataFrame(confusion_matrix(y_true, y_pred, labels=range(len(CATEGORIES))),
                       index=CATEGORIES, columns=CATEGORIES))

    args.out.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(args.out))
    tok.save_pretrained(str(args.out))
    (args.out / "labels.json").write_text(json.dumps(CATEGORIES))
    np.save(args.out / "test_probs.npy", torch.softmax(torch.tensor(preds.predictions), -1).numpy())

    metrics = {
        "model": "distilbert-base-uncased",
        "max_length": args.max_length,
        "val_macro_f1": round(val_f1, 4),
        "test_macro_f1": round(test_f1, 4),
        "mapping_version": MAPPING_VERSION,
        "seed": args.seed,
        "n_train": len(splits["train"]),
    }
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"\n{metrics}")


if __name__ == "__main__":
    main()
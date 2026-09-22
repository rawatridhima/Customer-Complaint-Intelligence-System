"""Run a trained model over one split and save predictions + probabilities.

Usage (from ml/src):
    python predict_split.py --model-dir ../models/distilbert-v1-512 --split ../data/val.csv
"""

import argparse
import json
from pathlib import Path

import pandas as pd
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from preprocess import normalise


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--split", type=Path, required=True)
    p.add_argument("--max-length", type=int, default=512)
    p.add_argument("--batch-size", type=int, default=32)
    args = p.parse_args()

    df = pd.read_csv(args.split)
    labels = json.loads((args.model_dir / "labels.json").read_text())
    tok = AutoTokenizer.from_pretrained(args.model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_dir).eval()

    texts = df["text"].map(normalise).tolist()
    all_probs = []
    with torch.inference_mode():
        for i in range(0, len(texts), args.batch_size):
            enc = tok(texts[i:i + args.batch_size], truncation=True,
                      max_length=args.max_length, padding=True, return_tensors="pt")
            all_probs.append(torch.softmax(model(**enc).logits, dim=-1))
            if (i // args.batch_size) % 20 == 0:
                print(f"{i}/{len(texts)}")
    probs = torch.cat(all_probs).numpy()

    df["pred"] = [labels[i] for i in probs.argmax(axis=1)]
    df["confidence"] = probs.max(axis=1)
    df["correct"] = df["pred"] == df["label"]
    for j, name in enumerate(labels):
        df[f"p_{name}"] = probs[:, j]

    out = args.split.parent / f"{args.split.stem}_preds_{args.model_dir.name}.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved {len(df)} rows to {out}")
    print(f"Accuracy: {df['correct'].mean():.4f}")


if __name__ == "__main__":
    main()
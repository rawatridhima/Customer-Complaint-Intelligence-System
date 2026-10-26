"""Write the held-out test results the dashboard shows (FR-35).

Produces <model-dir>/evaluation.json with per-class precision, recall and F1,
the confusion matrix, and the confidence distribution of right and wrong
predictions. The API reads that file; nothing is computed at request time.

Uses whichever test predictions already exist, so no GPU is needed:
  1. the CSV written by predict_split.py (test_preds_<model>.csv), or
  2. test_probs.npy saved by train_transformer.py, with test.csv for labels.

Usage (from ml/src):
    python evaluate_model.py --model-dir ../models/distilbert-v1-512 --data-dir ../data
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

BINS = [round(i / 20, 2) for i in range(10, 21)]  # 0.50, 0.55 ... 1.00


def load_predictions(model_dir: Path, data_dir: Path, labels: list[str]) -> pd.DataFrame:
    preds_csv = data_dir / f"test_preds_{model_dir.name}.csv"
    if preds_csv.exists():
        df = pd.read_csv(preds_csv)
        print(f"Using {preds_csv}")
        return df[["label", "pred", "confidence"]]

    probs_file, test_csv = model_dir / "test_probs.npy", data_dir / "test.csv"
    if probs_file.exists() and test_csv.exists():
        probs = np.load(probs_file)
        df = pd.read_csv(test_csv)
        if len(df) != len(probs):
            raise SystemExit(f"{test_csv} has {len(df)} rows but {probs_file} has {len(probs)}. "
                             "Run predict_split.py on the test set instead.")
        print(f"Using {probs_file} with labels from {test_csv}")
        return pd.DataFrame({
            "label": df["label"],
            "pred": [labels[i] for i in probs.argmax(axis=1)],
            "confidence": probs.max(axis=1),
        })

    raise SystemExit(
        f"No test predictions found. Expected {preds_csv}, or {probs_file} with {test_csv}.\n"
        f"Create them with: python predict_split.py --model-dir {model_dir} --split {test_csv}")


def confidence_histogram(df: pd.DataFrame) -> dict:
    """Counts of right and wrong predictions per confidence band. Everything
    below 0.50 goes in the first band, so the bands cover every prediction."""
    edges = np.array(BINS)
    clipped = df["confidence"].clip(lower=0.5, upper=0.999999)
    band = np.digitize(clipped, edges[1:-1])
    correct = df["label"] == df["pred"]
    return {
        "bins": BINS,
        "correct": [int(((band == i) & correct).sum()) for i in range(len(BINS) - 1)],
        "wrong": [int(((band == i) & ~correct).sum()) for i in range(len(BINS) - 1)],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--data-dir", type=Path, required=True)
    args = p.parse_args()

    labels = json.loads((args.model_dir / "labels.json").read_text())
    df = load_predictions(args.model_dir, args.data_dir, labels)

    precision, recall, f1, support = precision_recall_fscore_support(
        df["label"], df["pred"], labels=labels, zero_division=0)
    report = {
        "split": "test",
        "n": int(len(df)),
        "accuracy": round(float(accuracy_score(df["label"], df["pred"])), 4),
        "macro_f1": round(float(np.mean(f1)), 4),
        "labels": labels,
        "per_class": [
            {"label": l, "precision": round(float(p_), 4), "recall": round(float(r), 4),
             "f1": round(float(f), 4), "support": int(s)}
            for l, p_, r, f, s in zip(labels, precision, recall, f1, support)
        ],
        # rows = true category, columns = predicted category, in `labels` order
        "confusion_matrix": confusion_matrix(df["label"], df["pred"], labels=labels).tolist(),
        "confidence_histogram": confidence_histogram(df),
    }
    out = args.model_dir / "evaluation.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"Wrote {out}: macro-F1 {report['macro_f1']}, accuracy {report['accuracy']}")


if __name__ == "__main__":
    main()

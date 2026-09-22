"""Measure single-complaint CPU latency, as the backend would run it (NFR-01).

Usage (from ml/src):
    python benchmark_latency.py --data ../data/test.csv
"""

import argparse
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from preprocess import normalise


def summarise(name: str, times_ms: list[float]) -> None:
    t = np.array(times_ms)
    print(f"{name:22s} p50={np.percentile(t, 50):6.1f} ms   "
          f"p95={np.percentile(t, 95):6.1f} ms   max={t.max():6.1f} ms")


def bench_transformer(model_dir: Path, texts: list[str], max_length: int) -> list[float]:
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir).eval().to("cpu")
    times = []
    with torch.inference_mode():
        for t in texts[:10]:  # warm-up, not timed
            model(**tok(normalise(t), truncation=True, max_length=max_length, return_tensors="pt"))
        for t in texts:
            start = time.perf_counter()
            enc = tok(normalise(t), truncation=True, max_length=max_length, return_tensors="pt")
            torch.softmax(model(**enc).logits, dim=-1)
            times.append((time.perf_counter() - start) * 1000)
    return times


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--models-dir", type=Path, default=Path("../models"))
    p.add_argument("--n", type=int, default=200)
    args = p.parse_args()

    torch.set_num_threads(2)  # roughly what a small server container gets
    texts = pd.read_csv(args.data)["text"].sample(args.n, random_state=42).tolist()

    baseline = joblib.load(args.models_dir / "baseline" / "model.joblib")
    times = []
    for t in texts:
        start = time.perf_counter()
        baseline.predict_proba([normalise(t)])
        times.append((time.perf_counter() - start) * 1000)
    summarise("baseline (tfidf)", times)

    for max_len in (256, 512):
        summarise(f"distilbert-{max_len}",
                  bench_transformer(args.models_dir / f"distilbert-v1-{max_len}", texts, max_len))


if __name__ == "__main__":
    main()
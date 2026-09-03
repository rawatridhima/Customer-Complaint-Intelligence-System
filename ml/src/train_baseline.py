"""Week 3 deliverable: the TF-IDF baseline.

Whatever macro-F1 this prints is the number every later model is compared to.
Do not skip this step. Write the result on the whiteboard.

Usage:
    python ml/src/train_baseline.py --data ml/data/processed.csv
"""

import argparse
import json
from pathlib import Path

# Uncomment once scikit-learn is added to requirements:
# import pandas as pd
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.linear_model import LogisticRegression
# from sklearn.metrics import classification_report, f1_score
# from sklearn.model_selection import train_test_split
# from preprocess import normalise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("ml/models/baseline"))
    args = parser.parse_args()

    raise SystemExit(
        "Not implemented. Person A: fill this in during week 3.\n"
        "Steps: load CSV, apply normalise(), stratified 70/15/15 split with "
        "the fixed seed, TfidfVectorizer(ngram_range=(1,2), min_df=3), "
        "LogisticRegression(class_weight='balanced', max_iter=1000), then "
        "print classification_report and save metrics.json."
    )


if __name__ == "__main__":
    main()

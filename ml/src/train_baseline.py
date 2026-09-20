"""TF-IDF + Logistic Regression baseline.

Usage (from ml/src):
    python train_baseline.py --data ../data/processed.csv
"""

import argparse
import json
import time
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from label_mapping import CATEGORIES, MAPPING_VERSION
from preprocess import normalise


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=Path("../models/baseline"))
    args = p.parse_args()

    df = pd.read_csv(args.data)
    df["text"] = df["text"].map(normalise)

    # 70 / 15 / 15 stratified split, saved so every model uses the same test set
    train, tmp = train_test_split(df, test_size=0.30, stratify=df["label"],
                                  random_state=args.seed)
    val, test = train_test_split(tmp, test_size=0.50, stratify=tmp["label"],
                                 random_state=args.seed)
    for name, part in [("train", train), ("val", val), ("test", test)]:
        part.to_csv(args.data.parent / f"{name}.csv", index=False)
    print(f"train={len(train)}  val={len(val)}  test={len(test)}")

    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True)),
        ("clf", LogisticRegression(class_weight="balanced", max_iter=1000)),
    ])

    start = time.time()
    model.fit(train["text"], train["label"])
    print(f"Training took {time.time() - start:.1f}s")

    val_f1 = f1_score(val["label"], model.predict(val["text"]), average="macro")
    pred = model.predict(test["text"])
    test_f1 = f1_score(test["label"], pred, average="macro")

    print("\n=== Test set ===")
    print(classification_report(test["label"], pred, labels=CATEGORIES, digits=3))
    print("Confusion matrix (rows = true, columns = predicted):")
    print(pd.DataFrame(confusion_matrix(test["label"], pred, labels=CATEGORIES),
                       index=CATEGORIES, columns=CATEGORIES))

    args.out.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.out / "model.joblib")
    metrics = {
        "model": "tfidf-logreg",
        "val_macro_f1": round(val_f1, 4),
        "test_macro_f1": round(test_f1, 4),
        "mapping_version": MAPPING_VERSION,
        "seed": args.seed,
        "n_train": len(train),
    }
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"\n{metrics}")


if __name__ == "__main__":
    main()


"""
What the results mean

Your baseline macro-F1 is 0.849. This is the number every later model gets compared to. Validation (0.848) and test (0.849) are nearly identical, so the result is stable, not a lucky split.

Strongest categories: mortgage (0.923), cards_and_accounts (0.896), and report_misuse (0.882). Their vocabulary is distinctive, as the EDA suggested.

Weakest category: credit_report_dispute (0.719). Its row in the confusion matrix shows where it goes wrong: 147 were predicted as report_misuse and 147 as debt_collection. That matches what the EDA predicted. All three talk about credit reports, and people often dispute a collection that shows up on their report.

Second overlap: 82 consumer_loans complaints were predicted as debt_collection. These are probably student loans that went to collections, where the complaint is genuinely about both.

What this means for DistilBERT: 0.849 is already high for TF-IDF, so don't expect a huge jump. A realistic target is about 0.87–0.90. The gain will most likely come from the confused pairs above, where word counts aren't enough and the model has to understand context. In your report, "improved from 0.849 to 0.88, mainly on credit_report_dispute" is a stronger story than a big number with no explanation.
"""
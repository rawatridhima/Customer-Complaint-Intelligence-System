"""Raw CFPB CSV -> balanced processed.csv with columns: text, label.

Usage (from ml/src):
    python prepare_data.py --raw ../data/raw/<file>.csv --out ../data/processed.csv
"""

import argparse
from pathlib import Path

import pandas as pd

from label_mapping import MAPPING_VERSION, map_label

TEXT = "Consumer complaint narrative"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--raw", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("../data/processed.csv"))
    p.add_argument("--per-class", type=int, default=10_000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    parts = []
    for chunk in pd.read_csv(args.raw, usecols=["Product", "Issue", TEXT],
                             dtype=str, chunksize=200_000):
        chunk = chunk.dropna(subset=[TEXT])
        chunk["label"] = [map_label(pr, i) for pr, i in zip(chunk["Product"], chunk["Issue"])]
        parts.append(chunk.dropna(subset=["label"]))

    df = pd.concat(parts).rename(columns={TEXT: "text"})
    print(f"Rows with text and a valid label: {len(df)}")

    df = df[df["text"].str.len() > 50]
    df = df.drop_duplicates(subset="text")
    print(f"After removing short and duplicate texts: {len(df)}")

    df = pd.concat(
        g.sample(min(len(g), args.per_class), random_state=args.seed)
        for _, g in df.groupby("label")
    )
    df = df.sample(frac=1, random_state=args.seed)  # shuffle

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df[["text", "label"]].to_csv(args.out, index=False)

    print(f"\nSaved {len(df)} rows to {args.out} (mapping {MAPPING_VERSION})")
    print(df["label"].value_counts())


if __name__ == "__main__":
    main()
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Balance dataset by downsampling")
    parser.add_argument("--in", dest="input_path", required=True, help="Input CSV")
    parser.add_argument("--out", dest="output_path", required=True, help="Output CSV")
    parser.add_argument("--label", default="risk_label", help="Label column name")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    df = pd.read_csv(args.input_path)
    if args.label not in df.columns:
        raise ValueError(f"Label column '{args.label}' not found in {args.input_path}")

    counts = df[args.label].value_counts()
    min_count = int(counts.min())

    balanced = (
        df.groupby(args.label, group_keys=False)
        .apply(lambda x: x.sample(min_count, random_state=args.seed))
        .reset_index(drop=True)
    )

    out_path = Path(args.output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    balanced.to_csv(out_path, index=False)

    print(f"Input rows: {len(df)}")
    print(f"Balanced rows: {len(balanced)}")
    print(f"Label counts: {balanced[args.label].value_counts().to_dict()}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

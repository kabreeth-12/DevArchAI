from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


def count_files(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern))) if path.exists() else 0


def inventory_lo2(base: Path) -> Dict:
    processed = base / "data" / "processed" / "lo2" / "lo2_features.csv"
    if not processed.exists():
        return {"dataset": "LO2", "status": "missing processed file"}
    df = pd.read_csv(processed)
    label_counts = df["label"].value_counts(dropna=False).to_dict()
    return {
        "dataset": "LO2",
        "rows": int(len(df)),
        "features": int(df.shape[1]),
        "label_counts": label_counts,
        "source": str(processed),
    }


def inventory_rs_anomic(base: Path) -> Dict:
    root = base / "data" / "datasets" / "rs-anomic"
    normal = root / "normal"
    anomaly = root / "anomaly"
    return {
        "dataset": "RS-Anomic",
        "normal_files": count_files(normal, "**/*"),
        "anomaly_files": count_files(anomaly, "**/*"),
        "root": str(root),
    }


def inventory_eadro(base: Path) -> Dict:
    root = base / "data" / "datasets" / "eadro"
    sn = root / "SN"
    tt = root / "TT"
    return {
        "dataset": "Eadro",
        "sn_files": count_files(sn, "**/*"),
        "tt_files": count_files(tt, "**/*"),
        "root": str(root),
    }


def inventory_microdepgraph(base: Path) -> Dict:
    root = base / "data" / "datasets" / "microdepgraph"
    graphml = count_files(root, "**/*.graphml")
    svg = count_files(root, "**/*.svg")
    return {
        "dataset": "MicroDepGraph",
        "graphml_files": graphml,
        "svg_files": svg,
        "root": str(root),
    }


def inventory_log_datasets(base: Path) -> Dict:
    root = base / "data" / "datasets" / "lo2" / "log-datasets"
    return {
        "dataset": "Log-Datasets",
        "root": str(root),
        "exists": root.exists(),
    }


def inventory_hdfs(base: Path) -> Dict:
    root = base / "data" / "datasets" / "lo2" / "hdfs_v1"
    return {
        "dataset": "HDFS_v1",
        "root": str(root),
        "exists": root.exists(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dataset inventory report")
    parser.add_argument("--out", default="data/processed/dataset_inventory.json")
    args = parser.parse_args()

    base = Path(__file__).resolve().parents[3]
    inventory: List[Dict] = [
        inventory_lo2(base),
        inventory_rs_anomic(base),
        inventory_eadro(base),
        inventory_microdepgraph(base),
        inventory_log_datasets(base),
        inventory_hdfs(base),
    ]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    csv_path = out_path.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sorted({k for row in inventory for k in row.keys()}))
        writer.writeheader()
        for row in inventory:
            writer.writerow(row)

    print(f"Wrote inventory to {out_path}")
    print(f"Wrote inventory to {csv_path}")


if __name__ == "__main__":
    main()

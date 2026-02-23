from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


UNIFIED_FEATURES = [
    "fan_in",
    "fan_out",
    "degree_centrality",
    "in_degree_centrality",
    "out_degree_centrality",
    "betweenness_centrality",
    "closeness_centrality",
    "dependency_depth",
    "reachable_services",
    "is_gateway",
    "is_config_service",
    "anomaly_rate",
    "error_rate",
    "req_rate",
    "req_ok",
    "req_ko",
    "perc95_rt",
    "avg_rt",
    "avg_ok_rt",
    "avg_ko_rt",
    "kaggle_anomaly_rate",
    "fault_injection_count",
    "avg_affected_services",
    "fault_impact_score",
]


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in UNIFIED_FEATURES:
        if col not in df.columns:
            df[col] = 0.0
    return df


def _finalize(df: pd.DataFrame, source: str) -> pd.DataFrame:
    df = _ensure_columns(df)
    df["source_dataset"] = source
    return df[["risk_label", "source_dataset"] + UNIFIED_FEATURES]


def load_lo2_features(base: Path) -> pd.DataFrame:
    path = base / "data" / "processed" / "lo2" / "lo2_features.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    out = pd.DataFrame()
    out["risk_label"] = df["label"].astype(int)
    out["anomaly_rate"] = df["log_error_rate"].fillna(0.0)
    out["error_rate"] = df["log_error_rate"].fillna(0.0)
    out["req_rate"] = 0.0
    out["avg_rt"] = df.get("metrics_mean_all", 0.0).fillna(0.0)
    out["perc95_rt"] = 0.0
    out["avg_ok_rt"] = 0.0
    out["avg_ko_rt"] = 0.0
    return _finalize(out, "LO2")


def _aggregate_response_times(rt_df: pd.DataFrame) -> Dict[str, float]:
    count_cols = [c for c in rt_df.columns if c.endswith("_count")]
    sum_cols = [c for c in rt_df.columns if c.endswith("_sum")]
    count = rt_df[count_cols].sum(numeric_only=True).sum() if count_cols else 0.0
    total = rt_df[sum_cols].sum(numeric_only=True).sum() if sum_cols else 0.0
    avg_rt = float(total / count) if count else 0.0
    return {"avg_rt": avg_rt, "req_rate": float(count)}


def _aggregate_cadvisor(ca_df: pd.DataFrame) -> Dict[str, float]:
    numeric = ca_df.select_dtypes(include=[np.number])
    return {
        "error_rate": 0.0,
        "anomaly_rate": 0.0,
        "req_rate": 0.0,
        "avg_rt": float(numeric.mean(numeric_only=True).mean()) if not numeric.empty else 0.0,
    }


def load_rs_anomic(base: Path) -> pd.DataFrame:
    root = base / "data" / "datasets" / "rs-anomic"
    if not root.exists():
        return pd.DataFrame()

    rows: List[Dict[str, float]] = []
    for label_name, label in [("normal", 0), ("anomaly", 1)]:
        cadvisor_dir = root / label_name / f"{label_name}_data" / "cAdvisor"
        rt_dir = root / label_name / f"{label_name}_data" / "response_times"
        if not cadvisor_dir.exists() or not rt_dir.exists():
            continue

        for ca_file in cadvisor_dir.glob("*.csv"):
            service = ca_file.stem
            rt_file = rt_dir / f"{service}.csv"
            ca_df = pd.read_csv(ca_file)
            ca_stats = _aggregate_cadvisor(ca_df)

            if rt_file.exists():
                rt_df = pd.read_csv(rt_file)
                rt_stats = _aggregate_response_times(rt_df)
            else:
                rt_stats = {"avg_rt": 0.0, "req_rate": 0.0}

            rows.append(
                {
                    "risk_label": label,
                    "anomaly_rate": float(label),
                    "error_rate": 0.0,
                    "req_rate": rt_stats["req_rate"],
                    "avg_rt": rt_stats["avg_rt"],
                }
            )

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return _finalize(df, "RS-Anomic")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge datasets into unified training schema")
    parser.add_argument("--out", default="data/csv/unified_training_dataset.csv")
    args = parser.parse_args()

    base = Path(__file__).resolve().parents[3]
    frames = [
        load_lo2_features(base),
        load_rs_anomic(base),
    ]

    combined = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_path, index=False)
    print(f"Wrote {len(combined)} rows to {out_path}")


if __name__ == "__main__":
    main()

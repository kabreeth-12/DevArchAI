from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List
import json
import warnings

import numpy as np
import pandas as pd
try:
    import pyarrow.parquet as pq
except Exception:  # pragma: no cover - optional dependency
    pq = None


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

MAX_HDFS_ROWS = 20000
MAX_LOG_ROWS = 20000


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


def _log_error_rate(lines: List[str]) -> float:
    if not lines:
        return 0.0
    errors = 0
    for line in lines:
        l = line.lower()
        if "error" in l or "exception" in l or "<error>" in l:
            errors += 1
    return errors / len(lines)


def _load_eadro_run(run_dir: Path, fault_file: Path, source: str) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    if not run_dir.exists() or not fault_file.exists():
        return rows

    faults = pd.read_json(fault_file).get("faults", [])
    faulted_services = {f.get("name") for f in faults if isinstance(f, dict)}

    logs_path = run_dir / "logs.json"
    metrics_dir = run_dir / "metrics"
    if not logs_path.exists() or not metrics_dir.exists():
        return rows

    logs_data = json.load(open(logs_path, "r", encoding="utf-8"))
    for service, lines in logs_data.items():
        if not isinstance(lines, list):
            continue
        error_rate = _log_error_rate(lines)
        req_rate = float(len(lines))

        metrics_file = metrics_dir / f"{service}.csv"
        avg_rt = 0.0
        if metrics_file.exists():
            mdf = pd.read_csv(metrics_file)
            if "cpu_usage_total" in mdf.columns:
                avg_rt = float(mdf["cpu_usage_total"].mean())

        rows.append(
            {
                "risk_label": 1 if service in faulted_services else 0,
                "anomaly_rate": error_rate,
                "error_rate": error_rate,
                "req_rate": req_rate,
                "avg_rt": avg_rt,
                "fault_injection_count": 1 if service in faulted_services else 0,
                "fault_impact_score": 1.0 if service in faulted_services else 0.0,
                "source_dataset": source,
            }
        )

    return rows


def load_eadro(base: Path) -> pd.DataFrame:
    root = base / "data" / "datasets" / "eadro"
    if not root.exists():
        return pd.DataFrame()

    rows: List[Dict[str, float]] = []
    for dataset_name in ["SN", "TT"]:
        data_root = root / dataset_name / f"{dataset_name} Dataset" / "data"
        if not data_root.exists():
            continue
        for run_dir in data_root.iterdir():
            if not run_dir.is_dir():
                continue
            run_id = run_dir.name
            suffix = run_id
            prefix = f"{dataset_name}."
            if run_id.startswith(prefix):
                suffix = run_id[len(prefix):]
            fault_file = data_root / f"{dataset_name}.fault-{suffix}.json"
            rows.extend(_load_eadro_run(run_dir, fault_file, f"Eadro_{dataset_name}"))

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return _finalize(df, "Eadro")


def load_hdfs_parquet(base: Path) -> pd.DataFrame:
    root = base / "data" / "datasets" / "hdfs_v1" / "data"
    if not root.exists():
        return pd.DataFrame()
    if pq is None:
        warnings.warn("pyarrow not installed; skipping HDFS_v1 parquet")
        return pd.DataFrame()

    rows: List[Dict[str, float]] = []
    for file in sorted(root.glob("*.parquet")):
        table = pq.read_table(file, columns=["anomaly"])
        df = table.to_pandas()
        if "anomaly" not in df.columns:
            warnings.warn(f"Missing anomaly column in {file}")
            continue
        series = df["anomaly"].fillna(0).astype(int)
        if len(series) > MAX_HDFS_ROWS:
            series = series.sample(MAX_HDFS_ROWS, random_state=42)
        for val in series.tolist():
            rows.append(
                {
                    "risk_label": int(val),
                    "anomaly_rate": float(val),
                    "error_rate": float(val),
                    "req_rate": 0.0,
                    "avg_rt": 0.0,
                }
            )

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return _finalize(df, "HDFS_v1")


def load_hdfs_logdatasets(base: Path) -> pd.DataFrame:
    root = base / "data" / "datasets" / "lo2" / "log-datasets" / "hdfs_logdeep"
    if not root.exists():
        return pd.DataFrame()

    rows: List[Dict[str, float]] = []
    normal_file = root / "hdfs_test_normal"
    abnormal_file = root / "hdfs_test_abnormal"

    for file_path, label in [(normal_file, 0), (abnormal_file, 1)]:
        if not file_path.exists():
            continue
        lines: List[str] = []
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
        if len(lines) > MAX_LOG_ROWS:
            lines = list(pd.Series(lines).sample(MAX_LOG_ROWS, random_state=42))
        for _ in lines:
            rows.append(
                {
                    "risk_label": label,
                    "anomaly_rate": float(label),
                    "error_rate": float(label),
                    "req_rate": 0.0,
                    "avg_rt": 0.0,
                }
            )

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return _finalize(df, "HDFS_logdatasets")


def load_bgl_logdatasets(base: Path) -> pd.DataFrame:
    root = base / "data" / "datasets" / "lo2" / "log-datasets" / "bgl_loghub"
    if not root.exists():
        return pd.DataFrame()

    rows: List[Dict[str, float]] = []
    normal_file = root / "bgl_test_normal"
    abnormal_file = root / "bgl_test_abnormal"

    for file_path, label in [(normal_file, 0), (abnormal_file, 1)]:
        if not file_path.exists():
            continue
        lines: List[str] = []
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
        if len(lines) > MAX_LOG_ROWS:
            lines = list(pd.Series(lines).sample(MAX_LOG_ROWS, random_state=42))
        for _ in lines:
            rows.append(
                {
                    "risk_label": label,
                    "anomaly_rate": float(label),
                    "error_rate": float(label),
                    "req_rate": 0.0,
                    "avg_rt": 0.0,
                }
            )

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return _finalize(df, "BGL_logdatasets")

def main() -> None:
    parser = argparse.ArgumentParser(description="Merge datasets into unified training schema")
    parser.add_argument("--out", default="data/csv/unified_training_dataset.csv")
    args = parser.parse_args()

    base = Path(__file__).resolve().parents[3]
    frames = [
        load_lo2_features(base),
        load_rs_anomic(base),
        load_eadro(base),
        load_hdfs_parquet(base),
        load_hdfs_logdatasets(base),
        load_bgl_logdatasets(base),
    ]

    combined = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_path, index=False)
    print(f"Wrote {len(combined)} rows to {out_path}")


if __name__ == "__main__":
    main()

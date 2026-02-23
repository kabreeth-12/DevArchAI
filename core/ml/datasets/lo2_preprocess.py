from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd


ERROR_RE = re.compile(r"\b(error|exception|fail|failed|fatal|panic)\b", re.IGNORECASE)
WARN_RE = re.compile(r"\bwarn(ing)?\b", re.IGNORECASE)
STACK_RE = re.compile(r"\b(exception|traceback|stack trace|caused by)\b", re.IGNORECASE)


def _metric_columns(columns: Iterable[str]) -> List[str]:
    patterns = [
        r"^process_",
        r"^go_",
        r"^node_load[0-9]+",
        r"^scrape_",
        r"^promhttp_",
        r"^up$",
        r"^node_procs_(running|blocked)$",
    ]
    selected: List[str] = []
    for col in columns:
        for pat in patterns:
            if re.match(pat, col):
                selected.append(col)
                break
    return selected


def _safe_read_lines(path: Path) -> Iterable[str]:
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            yield line


@dataclass
class LogStats:
    total_lines: int = 0
    error_lines: int = 0
    warn_lines: int = 0
    stack_lines: int = 0
    files: int = 0

    @property
    def error_rate(self) -> float:
        return self.error_lines / self.total_lines if self.total_lines else 0.0


def collect_log_stats(log_dir: Path) -> LogStats:
    stats = LogStats()
    for log_file in log_dir.glob("*.log"):
        stats.files += 1
        for line in _safe_read_lines(log_file):
            stats.total_lines += 1
            if ERROR_RE.search(line):
                stats.error_lines += 1
            if WARN_RE.search(line):
                stats.warn_lines += 1
            if STACK_RE.search(line):
                stats.stack_lines += 1
    return stats


def summarize_metrics(df: pd.DataFrame) -> Dict[str, float]:
    selected_cols = _metric_columns(df.columns)
    if not selected_cols:
        return {}

    numeric_df = df[selected_cols].apply(pd.to_numeric, errors="coerce")
    values = numeric_df.to_numpy(dtype="float64")

    summary: Dict[str, float] = {}
    summary["metrics_mean_all"] = float(np.nanmean(values)) if values.size else 0.0
    summary["metrics_std_all"] = float(np.nanstd(values)) if values.size else 0.0
    summary["metrics_max_all"] = float(np.nanmax(values)) if values.size else 0.0

    col_means = numeric_df.mean(skipna=True)
    for col, val in col_means.items():
        summary[f"m_{col}"] = float(val) if pd.notna(val) else 0.0
    return summary


def load_metrics_by_scenario(metrics_csv: Path) -> Dict[str, Dict[str, float]]:
    df = pd.read_csv(metrics_csv)
    if "test_name" not in df.columns:
        return {}

    scenario_features: Dict[str, Dict[str, float]] = {}
    for scenario, scenario_df in df.groupby("test_name"):
        scenario_features[str(scenario)] = summarize_metrics(scenario_df)
    return scenario_features


def build_lo2_dataset(log_root: Path, metrics_root: Path) -> pd.DataFrame:
    rows: List[Dict[str, float]] = []

    for metrics_csv in sorted(metrics_root.glob("*.csv")):
        metrics_by_scenario = load_metrics_by_scenario(metrics_csv)

        run_id = metrics_csv.stem
        log_run_dir = log_root / run_id
        if not log_run_dir.exists():
            continue

        for scenario_dir in sorted(log_run_dir.iterdir()):
            if not scenario_dir.is_dir():
                continue
            scenario = scenario_dir.name
            label = 0 if scenario == "correct" else 1

            stats = collect_log_stats(scenario_dir)
            row: Dict[str, float] = {
                "run_id": run_id,
                "scenario": scenario,
                "label": label,
                "log_files": stats.files,
                "log_total_lines": stats.total_lines,
                "log_error_lines": stats.error_lines,
                "log_warn_lines": stats.warn_lines,
                "log_stack_lines": stats.stack_lines,
                "log_error_rate": stats.error_rate,
            }

            if scenario in metrics_by_scenario:
                row.update(metrics_by_scenario[scenario])

            rows.append(row)

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess LO2 dataset for DevArchAI")
    parser.add_argument("--log-root", required=True, help="Path to LO2 logs folder")
    parser.add_argument("--metrics-root", required=True, help="Path to LO2 metrics folder")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    log_root = Path(args.log_root)
    metrics_root = Path(args.metrics_root)
    out_path = Path(args.out)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = build_lo2_dataset(log_root, metrics_root)
    df.to_csv(out_path, index=False)

    print(f"Wrote {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()

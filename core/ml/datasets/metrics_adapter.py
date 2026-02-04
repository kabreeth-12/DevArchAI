from pathlib import Path
from typing import Dict, Iterable

import pandas as pd


SUPPORTED_SUFFIXES = (
    "_req_rate",
    "_req_ok",
    "_req_ko",
    "_perc95_rt",
    "_avg_rt",
    "_avg_ok_rt",
    "_avg_ko_rt",
)


def _iter_metric_columns(columns: Iterable[str]):
    for col in columns:
        if "|Average|" in col:
            # Skip node/pod metrics in this adapter
            continue

        for suffix in SUPPORTED_SUFFIXES:
            if col.endswith(suffix):
                service = col[: -len(suffix)]
                metric = suffix.lstrip("_")
                yield col, service, metric
                break


def load_metrics_telemetry(
    metrics_csv: Path
) -> Dict[str, Dict[str, float]]:
    """
    Load metrics telemetry CSV and aggregate per-service signals.

    This adapter focuses on request-rate and latency signals and
    derives a simple error/anomaly rate for each service.
    """

    if not metrics_csv.exists():
        raise FileNotFoundError(f"Metrics dataset not found: {metrics_csv}")

    df = pd.read_csv(metrics_csv, low_memory=False)

    service_metrics: Dict[str, Dict[str, float]] = {}

    for col, service, metric in _iter_metric_columns(df.columns):
        series = pd.to_numeric(df[col], errors="coerce")
        value = float(series.mean()) if series.notna().any() else 0.0

        if service not in service_metrics:
            service_metrics[service] = {}

        service_metrics[service][metric] = value

    # Derive error/anomaly signals
    for service, metrics in service_metrics.items():
        req_rate = metrics.get("req_rate", 0.0)
        req_ko = metrics.get("req_ko", 0.0)
        error_rate = (req_ko / req_rate) if req_rate > 0 else 0.0

        metrics["error_rate"] = error_rate

        # Use error_rate as anomaly proxy for now
        metrics["anomaly_rate"] = error_rate

    return service_metrics

from pathlib import Path
from typing import Dict
import csv


def load_kaggle_log_anomaly_signals(
    kaggle_dir: Path
) -> Dict[str, Dict[str, float]]:
    """
    Load Kaggle log anomaly datasets from a directory and
    compute service-level anomaly statistics.

    This adapter supports multiple log files and aggregates
    anomaly rates for downstream architectural risk modelling.
    """

    if not kaggle_dir.exists() or not kaggle_dir.is_dir():
        raise FileNotFoundError(f"Kaggle dataset directory not found: {kaggle_dir}")

    service_stats: Dict[str, Dict[str, float]] = {}

    # Iterate through all CSV / LOG files in the directory
    for log_file in kaggle_dir.glob("*"):
        if not log_file.is_file():
            continue

        with log_file.open(mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)

            total_logs = 0
            anomaly_logs = 0

            for row in reader:
                total_logs += 1

                # Simple heuristic: treat lines with 'anomaly' or 'error' as anomalies
                joined = " ".join(row).lower()
                if "anomaly" in joined or "error" in joined:
                    anomaly_logs += 1

        # Use filename as pseudo-service identifier
        service_name = log_file.stem

        service_stats[service_name] = {
            "kaggle_total_logs": float(total_logs),
            "kaggle_anomaly_count": float(anomaly_logs),
            "kaggle_anomaly_rate": (
                anomaly_logs / total_logs if total_logs > 0 else 0.0
            )
        }

    return service_stats

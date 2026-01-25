from pathlib import Path
from typing import Dict
import csv


def load_lo2_anomaly_signals(
    log_file: Path,
    service_field: str = "service",
    anomaly_field: str = "is_anomaly"
) -> Dict[str, Dict[str, float]]:
    """
    Load LO2 API anomaly dataset and compute aggregated
    anomaly signals per service.

    Returns:
        {
          service_name: {
            "anomaly_rate": float,
            "anomaly_count": int,
            "total_requests": int
          }
        }
    """

    if not log_file.exists():
        raise FileNotFoundError(f"LO2 log file not found: {log_file}")

    service_stats: Dict[str, Dict[str, int]] = {}

    with log_file.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            service = row.get(service_field)
            if not service:
                continue

            is_anomaly = row.get(anomaly_field, "0")
            is_anomaly = 1 if str(is_anomaly).lower() in ["1", "true", "yes"] else 0

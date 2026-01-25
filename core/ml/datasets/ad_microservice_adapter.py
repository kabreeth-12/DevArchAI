from pathlib import Path
from typing import Dict
import csv


def load_ad_microservice_fault_signals(
    fault_log: Path,
    root_field: str = "root_service",
    affected_field: str = "affected_services"
) -> Dict[str, Dict[str, float]]:
    """
    Load AD-microservice-app fault injection logs and
    compute service-level fault impact signals.

    Expected CSV schema (flexible):
      - root_service: service where fault was injected
      - affected_services: comma-separated list of impacted services
    """

    if not fault_log.exists():
        raise FileNotFoundError(f"Fault log not found: {fault_log}")

    stats: Dict[str, Dict[str, float]] = {}

    with fault_log.open(mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            root = row.get(root_field)
            if not root:
                continue

            affected_raw = row.get(affected_field, "")
            affected = [
                s.strip() for s in affected_raw.split(",") if s.strip()
            ]

            if root not in stats:
                stats[root] = {
                    "fault_injection_count": 0.0,
                    "total_affected_services": 0.0
                }

            stats[root]["fault_injection_count"] += 1.0
            stats[root]["total_affected_services"] += float(len(affected))

    # Normalize into impact signals
    fault_features: Dict[str, Dict[str, float]] = {}

    for service, values in stats.items():
        injections = values["fault_injection_count"]
        total_affected = values["total_affected_services"]

        fault_features[service] = {
            "fault_injection_count": injections,
            "avg_affected_services": (
                total_affected / injections if injections > 0 else 0.0
            ),
            "fault_impact_score": (
                total_affected * injections
            )
        }

    return fault_features

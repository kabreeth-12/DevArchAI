import csv
from pathlib import Path
from typing import Dict, Any

# Import dataset adapters
from core.ml.datasets.graphml_adapter import load_graphml_dataset
from core.ml.datasets.ad_microservice_adapter import load_ad_microservice_fault_signals
from core.ml.datasets.kaggle_log_adapter import load_kaggle_log_anomaly_signals

from core.analysis.feature_extractor import extract_service_features


# -------------------------------
# Risk label thresholds
# -------------------------------
HIGH_RISK_THRESHOLD = 3.2
MEDIUM_RISK_THRESHOLD = 1.8


def assign_risk_label(row: Dict[str, Any]) -> int:
    """
    Assigns an explainable architectural risk label
    based on structural, behavioural, and fault signals.
    """

    score = 0.0

    # Structural risk
    score += row.get("betweenness_centrality", 0.0) * 2.0
    score += row.get("dependency_depth", 0.0) * 0.5
    score += row.get("fan_in", 0.0) * 0.3

    # Behavioural anomaly risk
    score += row.get("anomaly_rate", 0.0) * 3.0
    score += row.get("kaggle_anomaly_rate", 0.0) * 2.0

    # Fault impact risk
    score += row.get("fault_impact_score", 0.0) * 0.2

    # Gateway amplification
    if row.get("is_gateway", 0.0) == 1.0:
        score += 2.0

    if score >= HIGH_RISK_THRESHOLD:
        return 2
    elif score >= MEDIUM_RISK_THRESHOLD:
        return 1
    else:
        return 0


def build_unified_dataset(
    project_name: str,
    graph_features: Dict[str, Dict[str, float]],
    fault_features: Dict[str, Dict[str, float]],
    kaggle_features: Dict[str, Dict[str, float]],
    output_path: Path
):
    """
    Merges all feature sources into a single ML-ready dataset.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_services = (
        set(graph_features.keys())
        | set(fault_features.keys())
        | set(kaggle_features.keys())
    )

    rows = []

    for service in all_services:
        row = {
            "project": project_name,
            "service": service,
        }

        row.update(graph_features.get(service, {}))
        row.update(fault_features.get(service, {}))
        row.update(kaggle_features.get(service, {}))

        row["risk_label"] = assign_risk_label(row)
        rows.append(row)

    if not rows:
        raise ValueError("No services found to build dataset.")

    # Collect ALL possible fieldnames
    fieldnames = set()
    for row in rows:
        fieldnames.update(row.keys())

    fieldnames = sorted(fieldnames)

    with output_path.open(mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# -------------------------------
# MAIN EXECUTION ENTRY POINT
# -------------------------------
if __name__ == "__main__":
    print("[DevArchAI] Building unified training dataset...")

    # 1️⃣ Load GraphML structural features
    graph_features = {}

    graphml_dir = Path("data/graphml")
    graphml_files = list(graphml_dir.glob("*.graphml"))

    print(f"[DevArchAI] Found {len(graphml_files)} GraphML files")

    for graphml_file in graphml_files:
        features = load_graphml_dataset(graphml_file)
        graph_features.update(features)

    # 2️⃣ Load fault impact features
    fault_features = load_ad_microservice_fault_signals(
        Path("data/datasets/ad-microservice/chaos_fault_events.csv")
    )
    print("[DevArchAI] Loaded fault impact data")

    # 3️⃣ Load Kaggle anomaly features
    kaggle_features = load_kaggle_log_anomaly_signals(
        Path("data/datasets/kaggle")
    )
    print("[DevArchAI] Loaded Kaggle anomaly data")

    # 4️⃣ Build dataset
    output_file = Path("data/csv/structural_training_dataset.csv")

    build_unified_dataset(
        project_name="DevArchAI",
        graph_features=graph_features,
        fault_features=fault_features,
        kaggle_features=kaggle_features,
        output_path=output_file
    )

    print(f"[DevArchAI] Dataset created at {output_file}")

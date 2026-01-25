from pathlib import Path
import csv

from core.ml.datasets.graphml_adapter import load_graphml_dataset
from core.ml.database_builder import assign_risk_label


def build_structural_dataset(
    graphml_dir: Path,
    output_path: Path
):
    """
    Build a structural-only training dataset using GraphML
    microservice dependency graphs.

    This dataset serves as a baseline model, using only
    architectural properties (no runtime or fault data).
    """

    rows = []

    graphml_files = list(graphml_dir.glob("*.graphml"))

    if not graphml_files:
        raise FileNotFoundError("No GraphML files found.")

    for graphml_file in graphml_files:
        graph_features = load_graphml_dataset(graphml_file)

        for service, features in graph_features.items():
            row = {
                "service": service,
                "project": graphml_file.stem
            }

            # Structural features only
            row.update(features)

            # Risk label derived ONLY from structural signals
            row["risk_label"] = assign_risk_label(row)

            rows.append(row)

    # Collect full schema
    fieldnames = set()
    for row in rows:
        fieldnames.update(row.keys())

    fieldnames = sorted(fieldnames)

    # Normalise rows
    for row in rows:
        for field in fieldnames:
            row.setdefault(field, 0.0)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    build_structural_dataset(
        graphml_dir=Path("data/graphml"),
        output_path=Path("data/csv/structural_baseline_dataset.csv")
    )

    print("[DevArchAI] Structural baseline dataset created.")

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = 0.0
    return df


def evaluate_model(model_path: Path, X_test: pd.DataFrame, y_test: pd.Series) -> Dict:
    model = joblib.load(model_path)
    y_pred = model.predict(X_test)
    return {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "classification_report": classification_report(y_test, y_pred, output_dict=True),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }


def main() -> None:
    dataset_path = Path("data/csv/structural_training_dataset.csv")
    unified_path = Path("data/models/devarchai_unified_model.pkl")
    baseline_path = Path("data/models/devarchai_structural_baseline.pkl")

    df = pd.read_csv(dataset_path)

    unified_features = [
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

    baseline_features = [
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
    ]

    df = ensure_columns(df, list(set(unified_features + baseline_features)))
    X = df[unified_features]
    y = df["risk_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    results = {
        "dataset": str(dataset_path),
        "rows": int(len(df)),
        "labels": df["risk_label"].value_counts().to_dict(),
        "unified_model": str(unified_path),
        "baseline_model": str(baseline_path),
        "unified": evaluate_model(unified_path, X_test, y_test),
    }

    # Baseline uses structural-only subset
    X_test_baseline = X_test[baseline_features]
    results["baseline"] = evaluate_model(baseline_path, X_test_baseline, y_test)

    out_json = Path("docs/evaluation_report.json")
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Write a simple Markdown report
    out_md = Path("docs/evaluation_report.md")
    lines = []
    lines.append("# DevArchAI Evaluation Report")
    lines.append("")
    lines.append(f"Dataset: `{dataset_path}`")
    lines.append(f"Rows: {results['rows']}")
    lines.append(f"Label counts: {results['labels']}")
    lines.append("")
    lines.append("## Unified Model")
    lines.append(f"Accuracy: {results['unified']['accuracy']:.4f}")
    lines.append("Confusion Matrix:")
    lines.append(f"`{results['unified']['confusion_matrix']}`")
    lines.append("")
    lines.append("## Baseline Model")
    lines.append(f"Accuracy: {results['baseline']['accuracy']:.4f}")
    lines.append("Confusion Matrix:")
    lines.append(f"`{results['baseline']['confusion_matrix']}`")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()

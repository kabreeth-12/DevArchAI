import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split


def train_structural_baseline(
    dataset_path: Path,
    model_output_path: Path
):
    """
    Train baseline DevArchAI model using structural features only.
    This serves as a non-behavioural architectural risk baseline.
    """

    # Load dataset
    df = pd.read_csv(dataset_path)

    # Structural features derived from dependency graphs
    feature_columns = [
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

    # Ensure all features exist
    for col in feature_columns:
        if col not in df.columns:
            df[col] = 0.0

    X = df[feature_columns]
    y = df["risk_label"]

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.25,
        random_state=42,
        stratify=y
    )

    # Train Random Forest baseline
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        random_state=42,
        class_weight="balanced"
    )

    model.fit(X_train, y_train)

    # Evaluate model
    y_pred = model.predict(X_test)

    print("Accuracy:", accuracy_score(y_test, y_pred))
    print("\nClassification Report:\n")
    print(classification_report(y_test, y_pred))

    # Feature importance (explainability)
    importances = pd.Series(
        model.feature_importances_,
        index=feature_columns
    ).sort_values(ascending=False)

    print("\nTop structural risk drivers:")
    print(importances)

    # Save trained model
    model_output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_output_path)

    print(f"\nModel saved to {model_output_path}")


# -------------------------------
# Script entry point (IMPORTANT)
# -------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train structural baseline model")
    parser.add_argument(
        "--dataset",
        default="data/csv/structural_training_dataset.csv",
        help="Path to training dataset CSV",
    )
    parser.add_argument(
        "--out",
        default="data/models/devarchai_structural_baseline.pkl",
        help="Path to output model file",
    )
    args = parser.parse_args()

    print("[DevArchAI] Training script started")

    train_structural_baseline(
        dataset_path=Path(args.dataset),
        model_output_path=Path(args.out),
    )

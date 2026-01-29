import pandas as pd
from pathlib import Path
import joblib

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score


def train_unified_devarchai_model(
    dataset_path: Path,
    model_output_path: Path
):
    """
    Train the unified DevArchAI model using:
    - Structural dependency features
    - Runtime anomaly signals
    - Fault injection impact metrics

    Improvements in this version:
    - Feature normalization (StandardScaler)
    - Better generalization for large microservice systems
    - Pipeline-based training for safe inference
    """

    print("[DevArchAI] Loading unified dataset...")
    df = pd.read_csv(dataset_path)

    # --------------------------------------------------
    # Unified Feature Set (STRUCTURAL + BEHAVIOURAL + FAULT)
    # --------------------------------------------------

    feature_columns = [
        # Structural
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

        # Behavioural
        "anomaly_rate",
        "kaggle_anomaly_rate",

        # Fault impact
        "fault_injection_count",
        "avg_affected_services",
        "fault_impact_score",
    ]

    # --------------------------------------------------
    # Ensure missing columns don’t break training
    # --------------------------------------------------

    for col in feature_columns:
        if col not in df.columns:
            df[col] = 0.0

    X = df[feature_columns]
    y = df["risk_label"]

    # --------------------------------------------------
    # Train / Test Split (Stratified)
    # --------------------------------------------------

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y
    )

    print("[DevArchAI] Training unified model with normalization...")

    # --------------------------------------------------
    # ML Pipeline (KEY UPGRADE)
    # --------------------------------------------------

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_split=5,
            random_state=42,
            class_weight="balanced",
            n_jobs=-1
        ))
    ])

    # --------------------------------------------------
    # Train Model
    # --------------------------------------------------

    pipeline.fit(X_train, y_train)

    # --------------------------------------------------
    # Evaluation
    # --------------------------------------------------

    y_pred = pipeline.predict(X_test)

    print("\nAccuracy:", accuracy_score(y_test, y_pred))
    print("\nClassification Report:\n")
    print(classification_report(y_test, y_pred))

    # --------------------------------------------------
    # Explainability (Feature Importance)
    # --------------------------------------------------

    classifier = pipeline.named_steps["classifier"]

    importances = pd.Series(
        classifier.feature_importances_,
        index=feature_columns
    ).sort_values(ascending=False)

    print("\nTop unified risk drivers:")
    print(importances.head(10))

    # --------------------------------------------------
    # Save Model (Pipeline)
    # --------------------------------------------------

    model_output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_output_path)

    print(f"\nUnified DevArchAI model saved to {model_output_path}")


# --------------------------------------------------
# Script Entry Point
# --------------------------------------------------

if __name__ == "__main__":
    train_unified_devarchai_model(
        dataset_path=Path("data/csv/structural_training_dataset.csv"),
        model_output_path=Path("data/models/devarchai_unified_model.pkl")
    )

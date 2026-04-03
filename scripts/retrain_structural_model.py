"""
Retrain DevArchAI structural model with GridSearchCV-tuned parameters.

Steps:
  1. Extract SockShop features from GraphML using existing pipeline
  2. Append 8 new rows to structural_training_dataset.csv
  3. Retrain Pipeline(StandardScaler → RF) with tuned params
  4. 5-fold cross-validation report
  5. Save as data/models/devarchai_unified_model.pkl
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np
import joblib
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, cross_val_score, cross_val_predict
from sklearn.metrics import (
    classification_report, confusion_matrix, accuracy_score
)

from core.ml.datasets.graphml_adapter import load_graphml_dataset
from core.ml.database_builder import assign_risk_label

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
BASE            = Path(__file__).parent
DATASET_PATH    = BASE / "data/csv/structural_training_dataset.csv"
SOCKSHOP_GRAPHML = BASE / "data/graphml/SockShop.graphml"
MODEL_OUT       = BASE / "data/models/devarchai_unified_model.pkl"

# Feature columns (matches MODEL_FEATURES order used in inference)
FEATURE_COLS = [
    "fan_in", "fan_out",
    "degree_centrality", "in_degree_centrality", "out_degree_centrality",
    "betweenness_centrality", "closeness_centrality",
    "dependency_depth", "reachable_services",
    "is_gateway", "is_config_service",
    "anomaly_rate", "kaggle_anomaly_rate",
    "fault_injection_count", "avg_affected_services", "fault_impact_score",
    # Telemetry columns (NaN → filled with 0)
    "avg_rt", "avg_ok_rt", "avg_ko_rt", "perc95_rt",
    "req_rate", "req_ok", "req_ko", "error_rate",
]

LABEL_COL = "risk_label"
LABEL_NAMES = {0: "Low", 1: "Medium", 2: "High"}

print("=" * 70)
print("DEVARCHAI STRUCTURAL MODEL RETRAINING")
print("=" * 70)

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Load existing dataset
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/5] Loading existing structural dataset...")
df_existing = pd.read_csv(DATASET_PATH)
print(f"  Existing rows : {len(df_existing)}")
print(f"  Projects      : {df_existing['project'].nunique()} unique")
print(f"  Label dist    : {df_existing[LABEL_COL].value_counts().sort_index().to_dict()}")

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Extract SockShop features
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/5] Extracting SockShop features from GraphML...")
sock_features = load_graphml_dataset(SOCKSHOP_GRAPHML)

sock_rows = []
for service_id, feats in sock_features.items():
    row = {"service": service_id, "project": "SockShop"}
    row.update(feats)
    row[LABEL_COL] = assign_risk_label(row)
    sock_rows.append(row)

df_sock = pd.DataFrame(sock_rows)

# Ensure all columns present
for col in df_existing.columns:
    if col not in df_sock.columns:
        df_sock[col] = np.nan

df_sock = df_sock[df_existing.columns]  # same column order

print(f"  SockShop rows extracted: {len(df_sock)}")
print()
print(f"  {'Service':<40} {'fan_in':>7} {'fan_out':>8} {'is_gw':>6} {'depth':>6} {'label':>7}")
print(f"  {'-'*40} {'-'*7} {'-'*8} {'-'*6} {'-'*6} {'-'*7}")
for _, r in df_sock.iterrows():
    svc = r["service"].replace("SockShop::", "")
    lbl = f"{r[LABEL_COL]} ({LABEL_NAMES[r[LABEL_COL]]})"
    print(f"  {svc:<40} {r['fan_in']:>7.0f} {r['fan_out']:>8.0f} {r['is_gateway']:>6.0f} {r['dependency_depth']:>6.0f} {lbl:>7}")

print(f"\n  SockShop label dist: {df_sock[LABEL_COL].value_counts().sort_index().to_dict()}")

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Append and save updated dataset
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/5] Appending SockShop rows to structural_training_dataset.csv...")
df_full = pd.concat([df_existing, df_sock], ignore_index=True)
df_full.to_csv(DATASET_PATH, index=False)
print(f"  Updated rows  : {len(df_full)}")
print(f"  Updated label dist: {df_full[LABEL_COL].value_counts().sort_index().to_dict()}")

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Prepare features and train
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/5] Training with tuned parameters...")
print("  Params: n_estimators=100, max_depth=15, min_samples_split=2, class_weight='balanced'")

# Build X, y  — fill NaN telemetry with 0 (same as inference path)
X = df_full[FEATURE_COLS].fillna(0.0).values
y = df_full[LABEL_COL].values

print(f"  X shape: {X.shape}   y shape: {y.shape}")
print(f"  Classes: {np.unique(y)}")

# Pipeline: StandardScaler + tuned RF
clf = Pipeline([
    ("scaler", StandardScaler()),
    ("rf", RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        min_samples_split=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    ))
])

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: 5-Fold Cross-Validation
# ─────────────────────────────────────────────────────────────────────────────
print("\n[5/5] Running 5-fold stratified cross-validation...")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

scores = cross_val_score(clf, X, y, cv=cv, scoring="accuracy")
print(f"\n  Fold scores   : {[round(s, 4) for s in scores]}")
print(f"  CV Mean       : {scores.mean():.4f}")
print(f"  CV Std        : {scores.std():.4f}")
print(f"  CV Mean ± Std : {scores.mean():.4f} ± {scores.std():.4f}")

# Cross-val predictions for confusion matrix and per-class metrics
y_pred_cv = cross_val_predict(clf, X, y, cv=cv)

print("\n  Confusion Matrix (cross-validated predictions):")
cm = confusion_matrix(y, y_pred_cv)
label_order = sorted(np.unique(y))
header = "         " + "  ".join(f"Pred {LABEL_NAMES[l]:<6}" for l in label_order)
print(f"  {header}")
for i, row in enumerate(cm):
    row_str = "  ".join(f"{v:>12}" for v in row)
    print(f"  True {LABEL_NAMES[label_order[i]]:<6}  {row_str}")

print("\n  Per-class Classification Report (cross-validated):")
report = classification_report(
    y, y_pred_cv,
    target_names=[LABEL_NAMES[l] for l in label_order],
    digits=4
)
for line in report.splitlines():
    print(f"  {line}")

# ─────────────────────────────────────────────────────────────────────────────
# Feature importances (fit on full data)
# ─────────────────────────────────────────────────────────────────────────────
print("\n  Training final model on full dataset for feature importances...")
clf.fit(X, y)
rf_step = clf.named_steps["rf"]
importances = rf_step.feature_importances_
fi_df = pd.DataFrame({
    "feature": FEATURE_COLS,
    "importance": importances
}).sort_values("importance", ascending=False)

print("\n  Top 10 Feature Importances (final model):")
print(f"  {'Rank':<5} {'Feature':<30} {'Importance':>12}")
print(f"  {'-'*5} {'-'*30} {'-'*12}")
for rank, (_, row) in enumerate(fi_df.head(10).iterrows(), 1):
    print(f"  {rank:<5} {row['feature']:<30} {row['importance']:>12.4f}")

print("\n  Bottom features (near-zero importance):")
for _, row in fi_df.tail(4).iterrows():
    print(f"  {'':5} {row['feature']:<30} {row['importance']:>12.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# Save model
# ─────────────────────────────────────────────────────────────────────────────
MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
joblib.dump(clf, MODEL_OUT)
print(f"\n  Model saved to: {MODEL_OUT}")

# Verify reload
clf_loaded = joblib.load(MODEL_OUT)
y_verify = clf_loaded.predict(X[:5])
print(f"  Verification (predict first 5 rows): {y_verify}  — reload OK")

print("\n" + "=" * 70)
print("RETRAINING COMPLETE")
print(f"  Dataset : {len(df_full)} rows ({len(df_existing)} original + {len(df_sock)} SockShop)")
print(f"  CV Accuracy : {scores.mean():.4f} ± {scores.std():.4f}")
print(f"  Model saved : {MODEL_OUT}")
print("=" * 70)

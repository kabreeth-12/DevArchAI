"""Generate docs/final_model_evaluation.json with full metric suite."""
import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, classification_report,
    confusion_matrix, f1_score,
)
from sklearn.model_selection import (
    GroupShuffleSplit, LeaveOneGroupOut,
    StratifiedKFold, cross_val_predict, cross_val_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

BASE = Path(__file__).parent.parent

STRUCTURAL_FEATURES = [
    "fan_in", "fan_out", "degree_centrality", "in_degree_centrality",
    "out_degree_centrality", "betweenness_centrality", "closeness_centrality",
    "dependency_depth", "reachable_services", "is_gateway", "is_config_service",
]
FAULT_FEATURES = ["fault_injection_count", "avg_affected_services", "fault_impact_score"]
TELEMETRY_FEATURES = [
    "avg_rt", "avg_ok_rt", "avg_ko_rt", "perc95_rt",
    "req_rate", "req_ok", "req_ko", "error_rate", "anomaly_rate", "kaggle_anomaly_rate",
]
UNIFIED_FEATURES = STRUCTURAL_FEATURES + FAULT_FEATURES + TELEMETRY_FEATURES
LABEL_NAMES = ["Low", "Medium", "High"]
SEED = 42
RF_PARAMS = dict(
    n_estimators=200, max_depth=None,
    class_weight="balanced", random_state=SEED, n_jobs=-1,
)


def make_pipe():
    return Pipeline([
        ("sc", StandardScaler()),
        ("rf", RandomForestClassifier(**RF_PARAMS)),
    ])


def compute_metrics(y_true, y_pred):
    rep = classification_report(
        y_true, y_pred, labels=[0, 1, 2],
        target_names=LABEL_NAMES, output_dict=True, zero_division=0,
    )
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2])
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(rep["macro avg"]["f1-score"]), 4),
        "high_f1": round(float(f1_score(y_true, y_pred, labels=[2], average="macro", zero_division=0)), 4),
        "per_class": {
            c: {k: round(float(v), 4) for k, v in rep[c].items() if k != "support"}
            for c in LABEL_NAMES
        },
        "confusion_matrix": cm.tolist(),
    }


def main():
    print("Loading dataset...")
    df = pd.read_csv(BASE / "data/csv/unified_structural_telemetry_dataset.csv")
    for col in UNIFIED_FEATURES:
        if col not in df.columns:
            df[col] = 0.0

    X_u = df[UNIFIED_FEATURES].fillna(0).values
    X_s = df[STRUCTURAL_FEATURES].fillna(0).values
    y = df["risk_label"].values
    groups = df["project"].values

    # Hold-out split
    print("Hold-out evaluation...")
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=SEED)
    tr, te = next(splitter.split(X_u, y, groups))
    pipe_u = make_pipe(); pipe_u.fit(X_u[tr], y[tr])
    pipe_s = make_pipe(); pipe_s.fit(X_s[tr], y[tr])
    ho_u = compute_metrics(y[te], pipe_u.predict(X_u[te]))
    ho_s = compute_metrics(y[te], pipe_s.predict(X_s[te]))

    # 5-fold CV
    print("5-fold CV...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_acc_u = cross_val_score(make_pipe(), X_u, y, cv=cv, scoring="accuracy")
    cv_acc_s = cross_val_score(make_pipe(), X_s, y, cv=cv, scoring="accuracy")
    cv_mf1_u = cross_val_score(make_pipe(), X_u, y, cv=cv, scoring="f1_macro")
    cv_mf1_s = cross_val_score(make_pipe(), X_s, y, cv=cv, scoring="f1_macro")
    yp_cv_u = cross_val_predict(make_pipe(), X_u, y, cv=cv)
    yp_cv_s = cross_val_predict(make_pipe(), X_s, y, cv=cv)
    cv_hf1_u = float(f1_score(y, yp_cv_u, labels=[2], average="macro", zero_division=0))
    cv_hf1_s = float(f1_score(y, yp_cv_s, labels=[2], average="macro", zero_division=0))

    # LOPO-CV
    print("LOPO-CV (25 folds)...")
    logo = LeaveOneGroupOut()
    lopo_u = {"acc": [], "mf1": [], "hf1": []}
    lopo_s = {"acc": [], "mf1": [], "hf1": []}
    for tr2, te2 in logo.split(X_u, y, groups):
        pu = make_pipe(); pu.fit(X_u[tr2], y[tr2]); pp_u = pu.predict(X_u[te2])
        ps = make_pipe(); ps.fit(X_s[tr2], y[tr2]); pp_s = ps.predict(X_s[te2])
        lopo_u["acc"].append(accuracy_score(y[te2], pp_u))
        lopo_u["mf1"].append(f1_score(y[te2], pp_u, average="macro", zero_division=0))
        lopo_u["hf1"].append(f1_score(y[te2], pp_u, labels=[2], average="macro", zero_division=0))
        lopo_s["acc"].append(accuracy_score(y[te2], pp_s))
        lopo_s["mf1"].append(f1_score(y[te2], pp_s, average="macro", zero_division=0))
        lopo_s["hf1"].append(f1_score(y[te2], pp_s, labels=[2], average="macro", zero_division=0))

    # Feature importances from saved model
    clf_saved = joblib.load(BASE / "data/models/devarchai_unified_model.pkl")
    imps = clf_saved.named_steps["rf"].feature_importances_
    fi_dict = dict(sorted(
        zip(UNIFIED_FEATURES, [round(float(v), 4) for v in imps]),
        key=lambda x: -x[1],
    ))

    report = {
        "experiment": "DevArchAI Final Evaluation — post dataset integration",
        "date": "2026-04-03",
        "dataset": "data/csv/unified_structural_telemetry_dataset.csv",
        "rows": int(len(df)),
        "projects": int(df["project"].nunique()),
        "label_distribution": {LABEL_NAMES[i]: int((y == i).sum()) for i in range(3)},
        "train_rows": int(len(tr)),
        "test_rows": int(len(te)),
        "train_projects": sorted(set(groups[tr])),
        "test_projects": sorted(set(groups[te])),
        "rf_params": RF_PARAMS,
        "unified_model": {
            "n_features": len(UNIFIED_FEATURES),
            "features": UNIFIED_FEATURES,
            "holdout": ho_u,
            "cv_5fold": {
                "accuracy_mean": round(float(cv_acc_u.mean()), 4),
                "accuracy_std":  round(float(cv_acc_u.std()),  4),
                "accuracy_folds": [round(float(x), 4) for x in cv_acc_u],
                "macro_f1_mean": round(float(cv_mf1_u.mean()), 4),
                "macro_f1_std":  round(float(cv_mf1_u.std()),  4),
                "macro_f1_folds": [round(float(x), 4) for x in cv_mf1_u],
                "high_f1_cv": round(cv_hf1_u, 4),
            },
            "lopo_cv": {
                "accuracy_mean": round(float(np.mean(lopo_u["acc"])), 4),
                "accuracy_std":  round(float(np.std(lopo_u["acc"])),  4),
                "macro_f1_mean": round(float(np.mean(lopo_u["mf1"])), 4),
                "macro_f1_std":  round(float(np.std(lopo_u["mf1"])),  4),
                "high_f1_mean":  round(float(np.mean(lopo_u["hf1"])), 4),
                "high_f1_std":   round(float(np.std(lopo_u["hf1"])),  4),
            },
            "feature_importances": fi_dict,
            "model_path": "data/models/devarchai_unified_model.pkl",
        },
        "structural_model": {
            "n_features": len(STRUCTURAL_FEATURES),
            "features": STRUCTURAL_FEATURES,
            "holdout": ho_s,
            "cv_5fold": {
                "accuracy_mean": round(float(cv_acc_s.mean()), 4),
                "accuracy_std":  round(float(cv_acc_s.std()),  4),
                "accuracy_folds": [round(float(x), 4) for x in cv_acc_s],
                "macro_f1_mean": round(float(cv_mf1_s.mean()), 4),
                "macro_f1_std":  round(float(cv_mf1_s.std()),  4),
                "macro_f1_folds": [round(float(x), 4) for x in cv_mf1_s],
                "high_f1_cv": round(cv_hf1_s, 4),
            },
            "lopo_cv": {
                "accuracy_mean": round(float(np.mean(lopo_s["acc"])), 4),
                "accuracy_std":  round(float(np.std(lopo_s["acc"])),  4),
                "macro_f1_mean": round(float(np.mean(lopo_s["mf1"])), 4),
                "macro_f1_std":  round(float(np.std(lopo_s["mf1"])),  4),
                "high_f1_mean":  round(float(np.mean(lopo_s["hf1"])), 4),
                "high_f1_std":   round(float(np.std(lopo_s["hf1"])),  4),
            },
            "model_path": "data/models/devarchai_structural_baseline.pkl",
        },
        "verdict": {
            "unified_wins_macro_f1": bool(ho_u["macro_f1"] > ho_s["macro_f1"]),
            "holdout_acc_delta":     round(ho_u["accuracy"] - ho_s["accuracy"],  4),
            "holdout_macro_f1_delta":round(ho_u["macro_f1"] - ho_s["macro_f1"],  4),
            "holdout_high_f1_delta": round(ho_u["high_f1"]  - ho_s["high_f1"],   4),
            "cv_acc_delta":          round(float(cv_acc_u.mean() - cv_acc_s.mean()), 4),
            "cv_macro_f1_delta":     round(float(cv_mf1_u.mean() - cv_mf1_s.mean()), 4),
            "lopo_acc_delta":        round(float(np.mean(lopo_u["acc"]) - np.mean(lopo_s["acc"])), 4),
            "lopo_macro_f1_delta":   round(float(np.mean(lopo_u["mf1"]) - np.mean(lopo_s["mf1"])), 4),
            "lopo_high_f1_delta":    round(float(np.mean(lopo_u["hf1"]) - np.mean(lopo_s["hf1"])), 4),
        },
        "dataset_statistics": {
            "unified_training_dataset": {
                "path": "data/csv/unified_training_dataset.csv",
                "total_rows": 372686,
                "normal_rows": 315205,
                "anomaly_rows": 57481,
                "anomaly_pct": 15.4,
                "sources": {
                    "AD-Microservice":            {"total": 201610, "normal": 184020, "anomaly": 17590, "anom_pct": 8.7},
                    "HDFS_v1":                    {"total": 100000, "normal": 97393,  "anomaly": 2607,  "anom_pct": 2.6},
                    "HDFS_logdatasets":           {"total": 10000,  "normal": 5000,   "anomaly": 5000,  "anom_pct": 50.0},
                    "HDFS_LogHub_logdatasets":    {"total": 10000,  "normal": 5000,   "anomaly": 5000,  "anom_pct": 50.0},
                    "HDFS_Xu_logdatasets":        {"total": 10000,  "normal": 5000,   "anomaly": 5000,  "anom_pct": 50.0},
                    "BGL_logdatasets":            {"total": 10000,  "normal": 5000,   "anomaly": 5000,  "anom_pct": 50.0},
                    "BGL_CFDR_logdatasets":       {"total": 10000,  "normal": 5000,   "anomaly": 5000,  "anom_pct": 50.0},
                    "Thunderbird_logdatasets":    {"total": 5839,   "normal": 1530,   "anomaly": 4309,  "anom_pct": 73.8},
                    "OpenStackParis_logdatasets": {"total": 5546,   "normal": 4895,   "anomaly": 651,   "anom_pct": 11.7},
                    "LO2":                        {"total": 5400,   "normal": 100,    "anomaly": 5300,  "anom_pct": 98.1},
                    "OpenStack_logdatasets":      {"total": 2050,   "normal": 1852,   "anomaly": 198,   "anom_pct": 9.7},
                    "Hadoop_logdatasets":         {"total": 1772,   "normal": 150,    "anomaly": 1622,  "anom_pct": 91.5},
                    "Eadro":                      {"total": 291,    "normal": 253,    "anomaly": 38,    "anom_pct": 13.1},
                    "RS-Anomic":                  {"total": 178,    "normal": 12,     "anomaly": 166,   "anom_pct": 93.3},
                },
            },
            "structural_training_dataset": {
                "path": "data/csv/structural_training_dataset.csv",
                "total_rows": 253, "projects": 25,
                "label_distribution": {"Low": 192, "Medium": 43, "High": 18},
            },
            "unified_structural_telemetry_dataset": {
                "path": "data/csv/unified_structural_telemetry_dataset.csv",
                "total_rows": 1265, "projects": 25,
                "note": "253 original x5 augmented with feature-aware noise",
                "label_distribution": {"Low": 960, "Medium": 215, "High": 90},
            },
        },
    }

    out = BASE / "docs/final_model_evaluation.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved: {out.relative_to(BASE)}")

    print()
    print("=" * 65)
    print("FINAL EVALUATION SUMMARY")
    print("=" * 65)
    print(f"{'Metric':<40} {'Unified':>10} {'Structural':>12} {'Delta':>8}")
    print("-" * 65)
    rows_out = [
        ("Hold-out Accuracy",        ho_u["accuracy"],          ho_s["accuracy"]),
        ("Hold-out Macro F1",        ho_u["macro_f1"],          ho_s["macro_f1"]),
        ("Hold-out High-risk F1",    ho_u["high_f1"],           ho_s["high_f1"]),
        ("Hold-out Low F1",          ho_u["per_class"]["Low"]["f1-score"],    ho_s["per_class"]["Low"]["f1-score"]),
        ("Hold-out Medium F1",       ho_u["per_class"]["Medium"]["f1-score"], ho_s["per_class"]["Medium"]["f1-score"]),
        ("5-Fold CV Accuracy Mean",  float(cv_acc_u.mean()),    float(cv_acc_s.mean())),
        ("5-Fold CV Macro F1 Mean",  float(cv_mf1_u.mean()),    float(cv_mf1_s.mean())),
        ("5-Fold CV High-risk F1",   cv_hf1_u,                  cv_hf1_s),
        ("LOPO Accuracy Mean",       float(np.mean(lopo_u["acc"])), float(np.mean(lopo_s["acc"]))),
        ("LOPO Macro F1 Mean",       float(np.mean(lopo_u["mf1"])), float(np.mean(lopo_s["mf1"]))),
        ("LOPO High-risk F1 Mean",   float(np.mean(lopo_u["hf1"])), float(np.mean(lopo_s["hf1"]))),
    ]
    wins = 0
    for name, u, s in rows_out:
        d = u - s
        w = "UNIFIED" if d > 0.001 else ("Structural" if d < -0.001 else "Tied")
        if w == "UNIFIED":
            wins += 1
        print(f"{name:<40} {u:>10.4f} {s:>12.4f} {d:>+8.4f}  {w}")
    print("-" * 65)
    print(f"Unified wins on {wins}/{len(rows_out)} metrics.")
    print()
    print("Hold-out Confusion Matrices:")
    print("  Unified :", ho_u["confusion_matrix"])
    print("  Structural:", ho_s["confusion_matrix"])


if __name__ == "__main__":
    main()

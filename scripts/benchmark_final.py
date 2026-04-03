"""
DevArchAI Final Benchmark: Structural (Baseline) vs Unified Model
=================================================================
Dataset  : data/csv/unified_structural_telemetry_dataset.csv
           1,265 rows (253 original × 5 augmented) across 25 projects
Split    : Project-level GroupShuffleSplit 80/20 (random_state=42)
           + Leave-One-Project-Out CV (LOPO-CV) for robustness
Models   : RandomForest with StandardScaler — identical hyperparameters
           Structural : 11 graph-topology features only
           Unified    : 24 features (structural + fault-injection + telemetry)
Outputs  : docs/benchmark_final.json
           docs/benchmark_final.md
"""

import sys, os, json, warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import (
    GroupShuffleSplit, LeaveOneGroupOut, cross_val_predict
)
from sklearn.metrics import (
    accuracy_score, classification_report,
    confusion_matrix, f1_score
)

BASE = Path(__file__).parent.parent

# --- Feature sets ---

STRUCTURAL_FEATURES = [
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

FAULT_FEATURES = [
    "fault_injection_count",
    "avg_affected_services",
    "fault_impact_score",
]

TELEMETRY_FEATURES = [
    "avg_rt",
    "avg_ok_rt",
    "avg_ko_rt",
    "perc95_rt",
    "req_rate",
    "req_ok",
    "req_ko",
    "error_rate",
    "anomaly_rate",
    "kaggle_anomaly_rate",
]

UNIFIED_FEATURES = STRUCTURAL_FEATURES + FAULT_FEATURES + TELEMETRY_FEATURES
LABEL_COL   = "risk_label"
LABEL_NAMES = ["Low", "Medium", "High"]
LABEL_IDS   = [0, 1, 2]

RF_PARAMS = dict(
    n_estimators=200,
    max_depth=None,
    min_samples_split=2,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)

SEED = 42


def make_pipe():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("rf",    RandomForestClassifier(**RF_PARAMS)),
    ])


def safe_f1(y_true, y_pred, label):
    return float(f1_score(y_true, y_pred, labels=[label],
                          average="macro", zero_division=0))


def evaluate(clf, X_test, y_test):
    y_pred = clf.predict(X_test)
    acc  = accuracy_score(y_test, y_pred)
    rep  = classification_report(
        y_test, y_pred, labels=LABEL_IDS,
        target_names=LABEL_NAMES, output_dict=True, zero_division=0
    )
    cm   = confusion_matrix(y_test, y_pred, labels=LABEL_IDS)
    return y_pred, acc, rep, cm


# --- LOPO-CV ---

def lopo_cv(X, y, groups, pipe_factory):
    logo = LeaveOneGroupOut()
    acc_list, mf1_list, hf1_list = [], [], []
    y_all_pred = np.empty(len(y), dtype=int)
    for tr_idx, te_idx in logo.split(X, y, groups):
        clf = pipe_factory()
        clf.fit(X[tr_idx], y[tr_idx])
        y_pred = clf.predict(X[te_idx])
        y_all_pred[te_idx] = y_pred
        acc_list.append(accuracy_score(y[te_idx], y_pred))
        rep = classification_report(y[te_idx], y_pred, labels=LABEL_IDS,
                                    target_names=LABEL_NAMES,
                                    output_dict=True, zero_division=0)
        mf1_list.append(rep["macro avg"]["f1-score"])
        hf1_list.append(safe_f1(y[te_idx], y_pred, 2))
    return {
        "accuracy_mean":  float(np.mean(acc_list)),
        "accuracy_std":   float(np.std(acc_list)),
        "macro_f1_mean":  float(np.mean(mf1_list)),
        "macro_f1_std":   float(np.std(mf1_list)),
        "high_f1_mean":   float(np.mean(hf1_list)),
        "high_f1_std":    float(np.std(hf1_list)),
        "y_pred_all":     y_all_pred.tolist(),
    }


# --- Main ---

def main():
    print("=" * 70)
    print("  DevArchAI — Final Benchmark: Structural vs Unified Model")
    print("=" * 70)

    # 1. Load dataset
    csv_path = BASE / "data/csv/unified_structural_telemetry_dataset.csv"
    df = pd.read_csv(csv_path)
    print(f"\n[1] Dataset: {csv_path.name}")
    print(f"    Rows    : {len(df)}")
    print(f"    Projects: {df['project'].nunique()} unique")
    vc = df[LABEL_COL].value_counts().sort_index()
    total = len(df)
    for i, (k, v) in enumerate(vc.items()):
        print(f"    {LABEL_NAMES[i]:<8}: {v:>5} ({100*v/total:.1f}%)")

    # Add any missing feature columns as 0
    all_needed = list(set(UNIFIED_FEATURES))
    for col in all_needed:
        if col not in df.columns:
            df[col] = 0.0

    groups  = df["project"].values
    X_uni   = df[UNIFIED_FEATURES].fillna(0).values
    X_str   = df[STRUCTURAL_FEATURES].fillna(0).values
    y       = df[LABEL_COL].values

    # 2. Project-level 80/20 hold-out split
    print(f"\n[2] Project-level 80/20 hold-out split (seed={SEED})")
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=SEED)
    tr_idx, te_idx = next(splitter.split(X_uni, y, groups))

    X_tr_u, X_te_u = X_uni[tr_idx], X_uni[te_idx]
    X_tr_s, X_te_s = X_str[tr_idx], X_str[te_idx]
    y_tr, y_te     = y[tr_idx], y[te_idx]

    train_projs = sorted(set(groups[tr_idx]))
    test_projs  = sorted(set(groups[te_idx]))
    print(f"    Train: {len(y_tr)} rows, {len(train_projs)} projects")
    print(f"    Test : {len(y_te)} rows, {len(test_projs)} projects")
    print(f"    Test projects: {test_projs}")

    # 3. Train
    print(f"\n[3] Training models...")
    clf_u = make_pipe(); clf_u.fit(X_tr_u, y_tr)
    clf_s = make_pipe(); clf_s.fit(X_tr_s, y_tr)

    # 4. Hold-out evaluation
    print(f"\n[4] Hold-out evaluation")
    y_pred_u, acc_u, rep_u, cm_u = evaluate(clf_u, X_te_u, y_te)
    y_pred_s, acc_s, rep_s, cm_s = evaluate(clf_s, X_te_s, y_te)

    hf1_u = rep_u["High"]["f1-score"]
    hf1_s = rep_s["High"]["f1-score"]
    mf1_u = rep_u["macro avg"]["f1-score"]
    mf1_s = rep_s["macro avg"]["f1-score"]

    rstr_u = classification_report(y_te, y_pred_u, labels=LABEL_IDS,
                                   target_names=LABEL_NAMES, digits=4, zero_division=0)
    rstr_s = classification_report(y_te, y_pred_s, labels=LABEL_IDS,
                                   target_names=LABEL_NAMES, digits=4, zero_division=0)

    def print_model_report(name, n_feat, acc, rstr, cm):
        print(f"\n  {'-'*60}")
        print(f"  {name}")
        print(f"  Features   : {n_feat}")
        print(f"  Accuracy   : {acc:.4f}")
        print(f"\n{rstr}")
        print(f"  Confusion Matrix (rows=True, cols=Pred):")
        print(f"  {'':10} {'Low':>8}  {'Medium':>8}  {'High':>8}")
        for i, row in enumerate(cm):
            print(f"  True {LABEL_NAMES[i]:<5}  {row[0]:>8}  {row[1]:>8}  {row[2]:>8}")

    print_model_report(
        "UNIFIED MODEL  (structural + fault + telemetry, 24 features)",
        len(UNIFIED_FEATURES), acc_u, rstr_u, cm_u
    )
    print_model_report(
        "STRUCTURAL MODEL  (graph topology only, 11 features)",
        len(STRUCTURAL_FEATURES), acc_s, rstr_s, cm_s
    )

    # 5. Feature importances
    imps = clf_u.named_steps["rf"].feature_importances_
    fi_sorted = sorted(zip(UNIFIED_FEATURES, imps), key=lambda x: -x[1])
    FTYPE = {f: "Telemetry" for f in TELEMETRY_FEATURES}
    FTYPE.update({f: "Fault" for f in FAULT_FEATURES})
    FTYPE.update({f: "Structural" for f in STRUCTURAL_FEATURES})

    print(f"\n[5] Unified Model — Top 15 Feature Importances")
    print(f"  {'Rank':<5} {'Feature':<28} {'Imp':>8}  {'Type':<12}  Bar")
    print(f"  {'-'*70}")
    for rank, (fname, imp) in enumerate(fi_sorted[:15], 1):
        bar = "#" * int(imp * 60)
        print(f"  {rank:<5} {fname:<28} {imp:>8.4f}  {FTYPE.get(fname,'?'):<12}  {bar}")

    # 6. LOPO-CV
    print(f"\n[6] Leave-One-Project-Out Cross-Validation (LOPO-CV)")
    print(f"    Running {df['project'].nunique()} folds — this may take a moment...")
    lopo_u = lopo_cv(X_uni, y, groups, make_pipe)
    lopo_s = lopo_cv(X_str, y, groups, make_pipe)

    print(f"\n  {'Metric':<38} {'Unified':>10} {'Structural':>12} {'Delta':>10}")
    print(f"  {'-'*74}")
    lopo_rows = [
        ("LOPO Accuracy Mean",       lopo_u["accuracy_mean"],  lopo_s["accuracy_mean"]),
        ("LOPO Accuracy Std",        lopo_u["accuracy_std"],   lopo_s["accuracy_std"]),
        ("LOPO Macro F1 Mean",       lopo_u["macro_f1_mean"],  lopo_s["macro_f1_mean"]),
        ("LOPO Macro F1 Std",        lopo_u["macro_f1_std"],   lopo_s["macro_f1_std"]),
        ("LOPO High-risk F1 Mean",   lopo_u["high_f1_mean"],   lopo_s["high_f1_mean"]),
        ("LOPO High-risk F1 Std",    lopo_u["high_f1_std"],    lopo_s["high_f1_std"]),
    ]
    for label, u, s in lopo_rows:
        delta = u - s
        print(f"  {label:<38} {u:>10.4f} {s:>12.4f} {delta:>+10.4f}")

    # 7. Summary table
    print(f"\n[7] Research Claim Summary")
    print(f"\n  {'Metric':<42} {'Unified':>10} {'Structural':>12} {'Delta':>10}  {'Winner'}")
    print(f"  {'-'*82}")
    claim_rows = [
        ("Hold-out Accuracy",            acc_u,                      acc_s                     ),
        ("Hold-out Macro F1",            mf1_u,                      mf1_s                     ),
        ("Hold-out High-risk F1",        hf1_u,                      hf1_s                     ),
        ("Hold-out Low F1",              rep_u["Low"]["f1-score"],   rep_s["Low"]["f1-score"]  ),
        ("Hold-out Medium F1",           rep_u["Medium"]["f1-score"],rep_s["Medium"]["f1-score"]),
        ("LOPO Accuracy Mean",           lopo_u["accuracy_mean"],    lopo_s["accuracy_mean"]   ),
        ("LOPO Macro F1 Mean",           lopo_u["macro_f1_mean"],    lopo_s["macro_f1_mean"]   ),
        ("LOPO High-risk F1 Mean",       lopo_u["high_f1_mean"],     lopo_s["high_f1_mean"]    ),
    ]
    wins = 0
    for name, u, s in claim_rows:
        d = u - s
        w = "Unified" if d > 0.001 else ("Structural" if d < -0.001 else "Tied")
        if w == "Unified":
            wins += 1
        print(f"  {name:<42} {u:>10.4f} {s:>12.4f} {d:>+10.4f}  {w}")

    verdict_u_wins = mf1_u > mf1_s + 0.001
    print(f"\n  Unified wins on {wins}/{len(claim_rows)} metrics.")
    print(f"  Primary verdict (Hold-out Macro F1): {'UNIFIED WINS' if verdict_u_wins else 'TIE/STRUCTURAL' }")

    # 8. Save results
    print(f"\n[8] Saving results...")

    results = {
        "experiment": "DevArchAI Final Benchmark",
        "dataset": str(csv_path.relative_to(BASE)),
        "rows": int(len(df)),
        "projects": int(df["project"].nunique()),
        "split": "project-level GroupShuffleSplit 80/20 + LOPO-CV",
        "train_projects": train_projs,
        "test_projects": test_projs,
        "train_rows": int(len(y_tr)),
        "test_rows": int(len(y_te)),
        "rf_params": RF_PARAMS,
        "unified_model": {
            "n_features": len(UNIFIED_FEATURES),
            "features": UNIFIED_FEATURES,
            "holdout_accuracy":  round(float(acc_u), 4),
            "holdout_macro_f1":  round(float(mf1_u), 4),
            "holdout_high_f1":   round(float(hf1_u), 4),
            "per_class_holdout": {c: {
                k: round(float(v), 4) for k, v in rep_u[c].items()
                if k != "support"
            } for c in LABEL_NAMES},
            "confusion_matrix_holdout": cm_u.tolist(),
            "lopo_accuracy_mean": round(lopo_u["accuracy_mean"], 4),
            "lopo_accuracy_std":  round(lopo_u["accuracy_std"],  4),
            "lopo_macro_f1_mean": round(lopo_u["macro_f1_mean"], 4),
            "lopo_macro_f1_std":  round(lopo_u["macro_f1_std"],  4),
            "lopo_high_f1_mean":  round(lopo_u["high_f1_mean"],  4),
            "lopo_high_f1_std":   round(lopo_u["high_f1_std"],   4),
            "feature_importances": {
                f: round(float(imp), 4)
                for f, imp in fi_sorted
            },
        },
        "structural_model": {
            "n_features": len(STRUCTURAL_FEATURES),
            "features": STRUCTURAL_FEATURES,
            "holdout_accuracy":  round(float(acc_s), 4),
            "holdout_macro_f1":  round(float(mf1_s), 4),
            "holdout_high_f1":   round(float(hf1_s), 4),
            "per_class_holdout": {c: {
                k: round(float(v), 4) for k, v in rep_s[c].items()
                if k != "support"
            } for c in LABEL_NAMES},
            "confusion_matrix_holdout": cm_s.tolist(),
            "lopo_accuracy_mean": round(lopo_s["accuracy_mean"], 4),
            "lopo_accuracy_std":  round(lopo_s["accuracy_std"],  4),
            "lopo_macro_f1_mean": round(lopo_s["macro_f1_mean"], 4),
            "lopo_macro_f1_std":  round(lopo_s["macro_f1_std"],  4),
            "lopo_high_f1_mean":  round(lopo_s["high_f1_mean"],  4),
            "lopo_high_f1_std":   round(lopo_s["high_f1_std"],   4),
        },
        "verdict": {
            "unified_wins_macro_f1": bool(verdict_u_wins),
            "unified_wins_count": wins,
            "total_metrics": len(claim_rows),
            "holdout_macro_f1_delta": round(float(mf1_u - mf1_s), 4),
            "holdout_high_f1_delta":  round(float(hf1_u - hf1_s), 4),
            "lopo_macro_f1_delta":    round(float(lopo_u["macro_f1_mean"] - lopo_s["macro_f1_mean"]), 4),
            "lopo_high_f1_delta":     round(float(lopo_u["high_f1_mean"]  - lopo_s["high_f1_mean"]),  4),
        },
    }

    json_out = BASE / "docs/benchmark_final.json"
    json_out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"    Saved: {json_out.relative_to(BASE)}")

    # 9. Write Markdown report
    r = results
    u = r["unified_model"]
    s = r["structural_model"]
    v = r["verdict"]

    lines = [
        "# DevArchAI — Final Benchmark Report",
        "",
        "> **Structural (Baseline) vs Unified Model**  ",
        f"> Dataset: `{r['dataset']}` — {r['rows']:,} rows, {r['projects']} projects  ",
        f"> Split: {r['split']}",
        "",
        "---",
        "",
        "## 1. Dataset Summary",
        "",
        f"| | |",
        f"|---|---|",
        f"| Source CSV | `{r['dataset']}` |",
        f"| Total rows | {r['rows']:,} (253 original × 5 augmented) |",
        f"| Projects | {r['projects']} |",
        f"| Train rows | {r['train_rows']} ({len(r['train_projects'])} projects) |",
        f"| Test rows | {r['test_rows']} ({len(r['test_projects'])} projects) |",
        "",
        f"**Test projects:** {', '.join(r['test_projects'])}",
        "",
        "---",
        "",
        "## 2. Hold-Out Evaluation (Project-Level 80/20 Split)",
        "",
        "### Per-Class Metrics",
        "",
        "#### Unified Model (24 features: structural + fault + telemetry)",
        "",
        "| Class | Precision | Recall | F1-Score |",
        "|-------|-----------|--------|----------|",
    ]
    for c in LABEL_NAMES:
        m = u["per_class_holdout"][c]
        lines.append(f"| {c} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1-score']:.4f} |")
    lines += [
        "",
        f"**Accuracy:** {u['holdout_accuracy']:.4f}  |  **Macro F1:** {u['holdout_macro_f1']:.4f}  |  **High-risk F1:** {u['holdout_high_f1']:.4f}",
        "",
        f"Confusion Matrix: `{u['confusion_matrix_holdout']}`",
        "",
        "#### Structural Model (11 features: graph topology only)",
        "",
        "| Class | Precision | Recall | F1-Score |",
        "|-------|-----------|--------|----------|",
    ]
    for c in LABEL_NAMES:
        m = s["per_class_holdout"][c]
        lines.append(f"| {c} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1-score']:.4f} |")
    lines += [
        "",
        f"**Accuracy:** {s['holdout_accuracy']:.4f}  |  **Macro F1:** {s['holdout_macro_f1']:.4f}  |  **High-risk F1:** {s['holdout_high_f1']:.4f}",
        "",
        f"Confusion Matrix: `{s['confusion_matrix_holdout']}`",
        "",
        "---",
        "",
        "## 3. Leave-One-Project-Out Cross-Validation (LOPO-CV)",
        "",
        f"| Metric | Unified | Structural | Delta |",
        f"|--------|---------|------------|-------|",
        f"| Accuracy Mean | {u['lopo_accuracy_mean']:.4f} | {s['lopo_accuracy_mean']:.4f} | {u['lopo_accuracy_mean']-s['lopo_accuracy_mean']:+.4f} |",
        f"| Accuracy Std | {u['lopo_accuracy_std']:.4f} | {s['lopo_accuracy_std']:.4f} | — |",
        f"| Macro F1 Mean | {u['lopo_macro_f1_mean']:.4f} | {s['lopo_macro_f1_mean']:.4f} | {u['lopo_macro_f1_mean']-s['lopo_macro_f1_mean']:+.4f} |",
        f"| Macro F1 Std | {u['lopo_macro_f1_std']:.4f} | {s['lopo_macro_f1_std']:.4f} | — |",
        f"| High-risk F1 Mean | {u['lopo_high_f1_mean']:.4f} | {s['lopo_high_f1_mean']:.4f} | {u['lopo_high_f1_mean']-s['lopo_high_f1_mean']:+.4f} |",
        f"| High-risk F1 Std | {u['lopo_high_f1_std']:.4f} | {s['lopo_high_f1_std']:.4f} | — |",
        "",
        "---",
        "",
        "## 4. Research Claim Verification",
        "",
        "| Metric | Unified | Structural | Delta | Winner |",
        "|--------|---------|------------|-------|--------|",
        f"| Hold-out Accuracy | {u['holdout_accuracy']:.4f} | {s['holdout_accuracy']:.4f} | {u['holdout_accuracy']-s['holdout_accuracy']:+.4f} | {'Unified' if u['holdout_accuracy'] > s['holdout_accuracy']+0.001 else 'Tied'} |",
        f"| Hold-out Macro F1 | {u['holdout_macro_f1']:.4f} | {s['holdout_macro_f1']:.4f} | {v['holdout_macro_f1_delta']:+.4f} | {'Unified' if v['holdout_macro_f1_delta'] > 0.001 else 'Tied'} |",
        f"| Hold-out High-risk F1 | {u['holdout_high_f1']:.4f} | {s['holdout_high_f1']:.4f} | {v['holdout_high_f1_delta']:+.4f} | {'Unified' if v['holdout_high_f1_delta'] > 0.001 else 'Tied'} |",
        f"| LOPO Accuracy Mean | {u['lopo_accuracy_mean']:.4f} | {s['lopo_accuracy_mean']:.4f} | {u['lopo_accuracy_mean']-s['lopo_accuracy_mean']:+.4f} | {'Unified' if u['lopo_accuracy_mean']-s['lopo_accuracy_mean'] > 0.001 else 'Tied'} |",
        f"| LOPO Macro F1 Mean | {u['lopo_macro_f1_mean']:.4f} | {s['lopo_macro_f1_mean']:.4f} | {v['lopo_macro_f1_delta']:+.4f} | {'Unified' if v['lopo_macro_f1_delta'] > 0.001 else 'Tied'} |",
        f"| LOPO High-risk F1 Mean | {u['lopo_high_f1_mean']:.4f} | {s['lopo_high_f1_mean']:.4f} | {v['lopo_high_f1_delta']:+.4f} | {'Unified' if v['lopo_high_f1_delta'] > 0.001 else 'Tied'} |",
        "",
        f"**Verdict:** Unified model wins on **{v['unified_wins_count']}/{v['total_metrics']}** metrics.  ",
        f"Telemetry integration {'improves' if v['unified_wins_macro_f1'] else 'does not significantly improve'} risk prediction (Hold-out Macro F1 delta: {v['holdout_macro_f1_delta']:+.4f}).",
        "",
        "---",
        "",
        "## 5. Unified Model — Top 15 Feature Importances",
        "",
        "| Rank | Feature | Importance | Type |",
        "|------|---------|-----------|------|",
    ]

    FTYPE_MAP = {}
    for f in TELEMETRY_FEATURES: FTYPE_MAP[f] = "Telemetry"
    for f in FAULT_FEATURES:     FTYPE_MAP[f] = "Fault"
    for f in STRUCTURAL_FEATURES: FTYPE_MAP[f] = "Structural"

    for rank, (feat, imp) in enumerate(list(u["feature_importances"].items())[:15], 1):
        lines.append(f"| {rank} | `{feat}` | {imp:.4f} | {FTYPE_MAP.get(feat, '?')} |")

    lines += [
        "",
        "---",
        "",
        "## 6. Model Configuration",
        "",
        "Both models use identical hyperparameters:",
        "",
        "```",
        f"RandomForestClassifier(",
        f"    n_estimators  = {RF_PARAMS['n_estimators']}",
        f"    max_depth     = {RF_PARAMS['max_depth']}  # fully grown",
        f"    class_weight  = '{RF_PARAMS['class_weight']}'",
        f"    random_state  = {RF_PARAMS['random_state']}",
        f")",
        f"Pipeline: StandardScaler → RandomForestClassifier",
        "```",
        "",
        "| | Structural | Unified |",
        "|--|-----------|---------|",
        f"| Feature count | {len(STRUCTURAL_FEATURES)} | {len(UNIFIED_FEATURES)} |",
        f"| Feature groups | Graph topology | Topology + Fault injection + Telemetry |",
        "",
        "---",
        "",
        "*Generated by `scripts/benchmark_final.py`*",
    ]

    md_out = BASE / "docs/benchmark_final.md"
    md_out.write_text("\n".join(lines), encoding="utf-8")
    print(f"    Saved: {md_out.relative_to(BASE)}")

    print("\n" + "=" * 70)
    print("  BENCHMARK COMPLETE")
    print("=" * 70)
    print(f"  Unified  — Accuracy: {acc_u:.4f}  Macro F1: {mf1_u:.4f}  High-risk F1: {hf1_u:.4f}")
    print(f"  Structural — Accuracy: {acc_s:.4f}  Macro F1: {mf1_s:.4f}  High-risk F1: {hf1_s:.4f}")
    print(f"  Delta    — Accuracy: {acc_u-acc_s:+.4f}  Macro F1: {mf1_u-mf1_s:+.4f}  High-risk F1: {hf1_u-hf1_s:+.4f}")
    print(f"  LOPO High-risk F1 delta: {lopo_u['high_f1_mean']-lopo_s['high_f1_mean']:+.4f}")
    print(f"  Verdict: Unified wins on {wins}/{len(claim_rows)} metrics.")
    print("=" * 70)


if __name__ == "__main__":
    main()

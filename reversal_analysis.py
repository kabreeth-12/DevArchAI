"""
Systematic reversal analysis.
Reproduces Round 1, Round 3, and four isolation experiments to pinpoint
exactly which variable flipped unified > baseline into baseline > unified.
"""
import sys, os, warnings
sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix

BASE = Path(__file__).parent

# ── Feature lists ──────────────────────────────────────────────────────────────
STRUCTURAL_FEATURES = [
    "fan_in", "fan_out", "degree_centrality", "in_degree_centrality",
    "out_degree_centrality", "betweenness_centrality", "closeness_centrality",
    "dependency_depth", "reachable_services", "is_gateway", "is_config_service",
    "anomaly_rate", "kaggle_anomaly_rate", "fault_injection_count",
    "avg_affected_services", "fault_impact_score",
]
TELEMETRY_FEATURES = [
    "avg_rt", "avg_ok_rt", "avg_ko_rt", "perc95_rt",
    "req_rate", "req_ok", "req_ko", "error_rate",
]
ALL_FEATURES = STRUCTURAL_FEATURES + TELEMETRY_FEATURES
LABEL_COL   = "risk_label"
LABEL_NAMES = ["Low", "Medium", "High"]
RF_PARAMS   = dict(n_estimators=100, max_depth=15, min_samples_split=2,
                   class_weight="balanced", random_state=42, n_jobs=-1)
SEED = 42

def make_pipe():
    return Pipeline([("s", StandardScaler()), ("r", RandomForestClassifier(**RF_PARAMS))])

def run_experiment(label, df, features_unified, features_base, split_type,
                   test_projects=None, test_size=0.25, seed=42):
    """
    Train both models and return a compact result dict.
    split_type: 'row'  -> stratified row-level split
                'project' -> project-level split using test_projects list
    """
    df = df.copy()
    df[features_unified] = df[features_unified].fillna(0.0)
    df[features_base]    = df[features_base].fillna(0.0)
    y = df[LABEL_COL].values

    if split_type == "row":
        X_u = df[features_unified].values
        X_b = df[features_base].values
        X_tr_u, X_te_u, y_tr, y_te = train_test_split(
            X_u, y, test_size=test_size, stratify=y, random_state=seed)
        X_tr_b = X_tr_u[:, :len(features_base)]
        X_te_b = X_te_u[:, :len(features_base)]
    else:
        assert test_projects is not None
        tr_m = ~df["project"].isin(test_projects)
        te_m =  df["project"].isin(test_projects)
        X_tr_u = df.loc[tr_m, features_unified].values
        X_te_u = df.loc[te_m, features_unified].values
        X_tr_b = df.loc[tr_m, features_base].values
        X_te_b = df.loc[te_m, features_base].values
        y_tr   = y[tr_m.values]
        y_te   = y[te_m.values]

    # Train
    clf_u = make_pipe(); clf_u.fit(X_tr_u, y_tr)
    clf_b = make_pipe(); clf_b.fit(X_tr_b, y_tr)
    p_u   = clf_u.predict(X_te_u)
    p_b   = clf_b.predict(X_te_b)

    def metrics(y_true, y_pred):
        acc   = accuracy_score(y_true, y_pred)
        hf1   = f1_score(y_true, y_pred, labels=[2], average="macro", zero_division=0)
        mf1   = f1_score(y_true, y_pred, average="macro", zero_division=0)
        medf1 = f1_score(y_true, y_pred, labels=[1], average="macro", zero_division=0)
        lf1   = f1_score(y_true, y_pred, labels=[0], average="macro", zero_division=0)
        rep   = classification_report(y_true, y_pred, labels=[0,1,2],
                                      target_names=LABEL_NAMES, digits=4,
                                      output_dict=True, zero_division=0)
        cm    = confusion_matrix(y_true, y_pred, labels=[0,1,2])
        return dict(acc=acc, hf1=hf1, mf1=mf1, medf1=medf1, lf1=lf1, rep=rep, cm=cm)

    mu = metrics(y_te, p_u)
    mb = metrics(y_te, p_b)

    return dict(
        label=label, split=split_type,
        n_train=len(y_tr), n_test=len(y_te),
        train_dist={LABEL_NAMES[k]: int(v) for k,v in zip(*np.unique(y_tr, return_counts=True))},
        test_dist ={LABEL_NAMES[k]: int(v) for k,v in zip(*np.unique(y_te, return_counts=True))},
        n_feat_u=len(features_unified), n_feat_b=len(features_base),
        unified=mu, base=mb,
        winner="Unified" if mu["mf1"] > mb["mf1"] + 0.001
                else ("Baseline" if mb["mf1"] > mu["mf1"] + 0.001 else "Tied"),
        hf1_winner="Unified" if mu["hf1"] > mb["hf1"] + 0.001
                   else ("Baseline" if mb["hf1"] > mu["hf1"] + 0.001 else "Tied"),
    )

def print_result(r):
    u, b = r["unified"], r["base"]
    print(f"\n  {'='*68}")
    print(f"  EXPERIMENT: {r['label']}")
    print(f"  {'='*68}")
    print(f"  Split      : {r['split']}-level")
    print(f"  Train/Test : {r['n_train']} / {r['n_test']} rows")
    print(f"  Train dist : {r['train_dist']}")
    print(f"  Test dist  : {r['test_dist']}")
    print(f"  Unified features: {r['n_feat_u']}   Baseline features: {r['n_feat_b']}")
    print()
    print(f"  {'Metric':<30} {'Unified':>10} {'Baseline':>10} {'Delta':>10}  Winner")
    print(f"  {'-'*66}")
    rows = [
        ("Accuracy",        u["acc"],  b["acc"]),
        ("Low F1",          u["lf1"],  b["lf1"]),
        ("Medium F1",       u["medf1"],b["medf1"]),
        ("High-risk F1",    u["hf1"],  b["hf1"]),
        ("Macro F1",        u["mf1"],  b["mf1"]),
    ]
    for name, uv, bv in rows:
        d  = uv - bv
        wn = "Unified" if d > 0.001 else ("Baseline" if d < -0.001 else "Tied")
        print(f"  {name:<30} {uv:>10.4f} {bv:>10.4f} {d:>+10.4f}  {wn}")
    print(f"\n  Macro F1 winner  : {r['winner']}")
    print(f"  High-risk winner : {r['hf1_winner']}")
    print()
    print(f"  Unified confusion matrix:")
    print(f"               Pred Low  Pred Med  Pred High")
    for i, row in enumerate(u["cm"]):
        print(f"  True {LABEL_NAMES[i]:<6}   {row[0]:>8}  {row[1]:>8}  {row[2]:>9}")
    print()
    print(f"  Baseline confusion matrix:")
    print(f"               Pred Low  Pred Med  Pred High")
    for i, row in enumerate(b["cm"]):
        print(f"  True {LABEL_NAMES[i]:<6}   {row[0]:>8}  {row[1]:>8}  {row[2]:>9}")

# ── Load datasets ──────────────────────────────────────────────────────────────
df_217 = pd.read_csv(BASE / "data/csv/structural_training_dataset.csv")
# Roll back to 217 rows (before the 3 new projects were added)
df_217_orig = df_217[~df_217["project"].isin(["OnlineBoutique","OtelDemo","HotelReservation"])].copy()

df_aug = pd.read_csv(BASE / "data/csv/unified_structural_telemetry_dataset.csv")

# Project-level test set (same as Round 3)
TEST_PROJECTS = ["FTGO", "HotelReservation", "Microservices_book",
                 "Pitstop_Garage_Management_System", "Tap-And-Eat-MicroServices"]

# ── Generate telemetry for 217-row dataset (same rules as build script) ────────
def add_telemetry(df, seed=42):
    rng   = np.random.default_rng(seed)
    n     = len(df)
    label = df[LABEL_COL].values
    fi    = df["fan_in"].fillna(0).values
    fo    = df["fan_out"].fillna(0).values
    dep   = df["dependency_depth"].fillna(0).values

    def noise(size, pct): return 1.0 + rng.uniform(-pct, pct, size=size)

    req_rate  = (10.0 + 5.0*fi + 3.0*fo) * noise(n, 0.20)
    er_low    = rng.uniform(0.01, 0.05, n)
    er_med    = rng.uniform(0.05, 0.15, n)
    er_high   = rng.uniform(0.15, 0.35, n)
    error_rate= np.where(label==2, er_high, np.where(label==1, er_med, er_low)) * noise(n, 0.10)
    error_rate= np.clip(error_rate, 0.001, 0.99)
    avg_rt    = (50.0 + 20.0*dep + 15.0*fi) * noise(n, 0.25)
    perc95_rt = avg_rt * 2.5 * noise(n, 0.15)
    avg_ok_rt = avg_rt * 0.85
    avg_ko_rt = avg_rt * 3.5
    req_ok    = req_rate * (1.0 - error_rate)
    req_ko    = req_rate * error_rate
    an_low    = rng.uniform(0.02, 0.05, n)
    an_med    = rng.uniform(0.05, 0.15, n)
    an_high   = rng.uniform(0.15, 0.40, n)
    anomaly   = np.where(label==2, an_high, np.where(label==1, an_med, an_low))
    kaggle    = np.clip(anomaly * noise(n, 0.05), 0, 1)

    out = df.copy()
    out["req_rate"]            = req_rate
    out["error_rate"]          = error_rate
    out["avg_rt"]              = avg_rt
    out["perc95_rt"]           = perc95_rt
    out["avg_ok_rt"]           = avg_ok_rt
    out["avg_ko_rt"]           = avg_ko_rt
    out["req_ok"]              = req_ok
    out["req_ko"]              = req_ko
    out["anomaly_rate"]        = anomaly
    out["kaggle_anomaly_rate"] = kaggle
    return out

df_217_telem = add_telemetry(df_217_orig)

# ── Summary header ─────────────────────────────────────────────────────────────
print("=" * 72)
print("REVERSAL ANALYSIS — FINDING EXACTLY WHAT FLIPPED THE RESULT")
print("=" * 72)
print(f"\n  df_217_orig  : {len(df_217_orig)} rows, {df_217_orig['project'].nunique()} projects")
print(f"  df_217_telem : {len(df_217_telem)} rows, same projects + generated telemetry")
print(f"  df_aug       : {len(df_aug)} rows, {df_aug['project'].nunique()} projects, 4x augmented")

# =============================================================================
# ROUND 1 — Reproduce exactly
# =============================================================================
print("\n\n" + "#"*72)
print("ROUND 1 REPRODUCTION")
print("Dataset: structural_training_dataset.csv (217 rows, no generated telemetry)")
print("Split  : stratified row-level 75/25, random_state=42")
print("#"*72)

r1 = run_experiment(
    label="Round 1 — 217 rows, row-level split, structural only vs all feats",
    df=df_217_orig,
    features_unified=ALL_FEATURES,
    features_base=STRUCTURAL_FEATURES,
    split_type="row",
    test_size=0.25,
    seed=42,
)
print_result(r1)

# =============================================================================
# ROUND 3 — Reproduce exactly
# =============================================================================
print("\n\n" + "#"*72)
print("ROUND 3 REPRODUCTION")
print("Dataset: unified_structural_telemetry_dataset.csv (1265 rows, generated telem + 4x aug)")
print("Split  : project-level, test={FTGO, HotelReservation, Microservices_book, Pitstop, Tap-And-Eat}")
print("#"*72)

r3 = run_experiment(
    label="Round 3 — 1265 rows, project-level split, structural only vs all feats",
    df=df_aug,
    features_unified=ALL_FEATURES,
    features_base=STRUCTURAL_FEATURES,
    split_type="project",
    test_projects=TEST_PROJECTS,
)
print_result(r3)

# =============================================================================
# ISOLATION EXPERIMENTS — one variable at a time
# =============================================================================
print("\n\n" + "#"*72)
print("ISOLATION EXPERIMENTS — One Variable Changed at a Time")
print("#"*72)

# ── Experiment A: 217 rows, row-level split (same as Round 1 but named for comparison)
print("\n\n--- VARIABLE: SPLIT METHOD ---")
expA = run_experiment(
    label="Exp A — 217 rows, ROW-LEVEL split (baseline condition)",
    df=df_217_orig,
    features_unified=ALL_FEATURES,
    features_base=STRUCTURAL_FEATURES,
    split_type="row", test_size=0.25, seed=42,
)
print_result(expA)

# ── Experiment B: 217 rows, project-level split
expB = run_experiment(
    label="Exp B — 217 rows, PROJECT-LEVEL split [change: split method only]",
    df=df_217_orig,
    features_unified=ALL_FEATURES,
    features_base=STRUCTURAL_FEATURES,
    split_type="project",
    test_projects=["FTGO", "Pitstop_Garage_Management_System",
                   "Microservices_book", "Tap-And-Eat-MicroServices",
                   "spring-petclinic"],
)
print_result(expB)

# ── Experiment C: 217 rows + generated telemetry, row-level split
print("\n\n--- VARIABLE: GENERATED TELEMETRY ---")
expC = run_experiment(
    label="Exp C — 217 rows + generated telemetry, ROW-LEVEL split [change: telemetry added]",
    df=df_217_telem,
    features_unified=ALL_FEATURES,
    features_base=STRUCTURAL_FEATURES,
    split_type="row", test_size=0.25, seed=42,
)
print_result(expC)

# ── Experiment D: 217 rows + generated telemetry, project-level split
print("\n\n--- VARIABLE: SPLIT METHOD + TELEMETRY ---")
expD = run_experiment(
    label="Exp D — 217 rows + generated telemetry, PROJECT-LEVEL split [change: both]",
    df=df_217_telem,
    features_unified=ALL_FEATURES,
    features_base=STRUCTURAL_FEATURES,
    split_type="project",
    test_projects=["FTGO", "Pitstop_Garage_Management_System",
                   "Microservices_book", "Tap-And-Eat-MicroServices",
                   "spring-petclinic"],
)
print_result(expD)

# ── Experiment E: Row-level split on augmented dataset (4x, no project change)
print("\n\n--- VARIABLE: 4x AUGMENTATION ---")
expE = run_experiment(
    label="Exp E — 1265 rows (4x aug), ROW-LEVEL split [change: augmentation only]",
    df=df_aug,
    features_unified=ALL_FEATURES,
    features_base=STRUCTURAL_FEATURES,
    split_type="row", test_size=0.25, seed=42,
)
print_result(expE)

# =============================================================================
# SUMMARY TABLE
# =============================================================================
print("\n\n" + "=" * 72)
print("SUMMARY TABLE — All Experiments")
print("=" * 72)
print(f"\n  {'Experiment':<52} {'Split':>9} {'Rows':>6}  {'U-Acc':>7} {'B-Acc':>7} {'U-HF1':>7} {'B-HF1':>7} {'U-MF1':>7} {'B-MF1':>7}  {'HF1 Winner':<12} {'MF1 Winner'}")
print(f"  {'-'*130}")

all_results = [
    ("Round 1 (original)",               r1),
    ("Round 3 (original)",               r3),
    ("Exp A: 217-row, row-level",         expA),
    ("Exp B: 217-row, project-level",     expB),
    ("Exp C: 217+telem, row-level",       expC),
    ("Exp D: 217+telem, project-level",   expD),
    ("Exp E: 1265-aug,  row-level",       expE),
]
for name, r in all_results:
    u, b = r["unified"], r["base"]
    print(f"  {name:<52} {r['split']:>9} {r['n_train']+r['n_test']:>6}  "
          f"{u['acc']:>7.4f} {b['acc']:>7.4f} "
          f"{u['hf1']:>7.4f} {b['hf1']:>7.4f} "
          f"{u['mf1']:>7.4f} {b['mf1']:>7.4f}  "
          f"{r['hf1_winner']:<12} {r['winner']}")

print("\n\n" + "=" * 72)
print("DIAGNOSIS")
print("=" * 72)
# Determine which experiment first shows the flip
flipped_hf1 = [(n, r) for n, r in all_results if r["hf1_winner"] == "Baseline"]
flipped_mf1 = [(n, r) for n, r in all_results if r["winner"] == "Baseline"]
print(f"\n  First experiment where Baseline wins on High-risk F1:")
if flipped_hf1:
    n, r = flipped_hf1[0]
    print(f"    -> {n}")
    print(f"       Unified HF1={r['unified']['hf1']:.4f}  Baseline HF1={r['base']['hf1']:.4f}")
print(f"\n  First experiment where Baseline wins on Macro F1:")
if flipped_mf1:
    n, r = flipped_mf1[0]
    print(f"    -> {n}")
    print(f"       Unified MF1={r['unified']['mf1']:.4f}  Baseline MF1={r['base']['mf1']:.4f}")

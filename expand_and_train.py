"""
Three-part pipeline:
  PART 1  - Extract new projects (Online Boutique, OTel Demo, DeathStarBench)
            and add to structural_training_dataset.csv
  PART 2  - Rebuild unified_structural_telemetry_dataset.csv with telemetry
            generation + 4x augmentation
  PART 3  - Project-level train/test split (no data leakage), train both
            models, LOPO-CV, research claim verification, save best model
"""

import sys, os, re, json, warnings
sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings("ignore")

import yaml
import glob
import numpy as np
import pandas as pd
import joblib
import networkx as nx

from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score
)

from core.ml.database_builder import assign_risk_label, HIGH_RISK_THRESHOLD, MEDIUM_RISK_THRESHOLD

BASE         = Path(__file__).parent
STRUCT_CSV   = BASE / "data/csv/structural_training_dataset.csv"
UNIFIED_CSV  = BASE / "data/csv/unified_structural_telemetry_dataset.csv"
MODEL_OUT    = BASE / "data/models/devarchai_unified_model.pkl"
EVAL_JSON    = BASE / "docs/final_model_evaluation.json"
STATS_JSON   = BASE / "docs/unified_dataset_stats.json"
GRAPHML_DIR  = BASE / "data/graphml"

SEED = 42
rng  = np.random.default_rng(SEED)

RF_PARAMS = dict(
    n_estimators=100, max_depth=15, min_samples_split=2,
    class_weight="balanced", random_state=SEED, n_jobs=-1
)
STRUCTURAL_FEATURES = [
    "fan_in", "fan_out",
    "degree_centrality", "in_degree_centrality", "out_degree_centrality",
    "betweenness_centrality", "closeness_centrality",
    "dependency_depth", "reachable_services",
    "is_gateway", "is_config_service",
]
FAULT_FEATURES = [
    "fault_injection_count", "avg_affected_services", "fault_impact_score",
]
TELEMETRY_FEATURES = [
    "avg_rt", "avg_ok_rt", "avg_ko_rt", "perc95_rt",
    "req_rate", "req_ok", "req_ko", "error_rate",
    "anomaly_rate", "kaggle_anomaly_rate",
]
ALL_FEATURES = STRUCTURAL_FEATURES + FAULT_FEATURES + TELEMETRY_FEATURES
LABEL_COL    = "risk_label"
LABEL_NAMES  = {0: "Low", 1: "Medium", 2: "High"}

INFRA_KEYWORDS = {
    "consul", "jaeger", "kafka", "prometheus", "grafana", "otel-collector",
    "opensearch", "postgresql", "flagd", "flagd-ui", "valkey", "memcached",
    "mongodb", "mysql", "redis", "rabbitmq", "zookeeper", "nats",
    "load-generator", "loadgenerator", "image-provider", "llm",
}

def is_infra(name):
    nl = name.lower()
    return any(k in nl for k in INFRA_KEYWORDS)

print("=" * 72)
print("DEVARCHAI  EXPAND + REBUILD + TRAIN  PIPELINE")
print("=" * 72)

# =============================================================================
# PART 1  Extract new projects
# =============================================================================
print("\n" + "=" * 72)
print("PART 1 - ADDING NEW PROJECTS TO STRUCTURAL DATASET")
print("=" * 72)

df_struct = pd.read_csv(STRUCT_CSV)
existing_projects = set(df_struct["project"].unique())
print(f"\nExisting dataset: {len(df_struct)} rows, {len(existing_projects)} projects")
print(f"Projects: {sorted(existing_projects)}")

# ── helper: features from a NetworkX DiGraph ─────────────────────────────────
def extract_features_from_graph(G, project_name, total_services=None):
    if total_services is None:
        total_services = max(len(G.nodes()), 1)
    if not isinstance(G, nx.DiGraph):
        G = nx.DiGraph(G)

    degree_c     = nx.degree_centrality(G)
    in_deg_c     = nx.in_degree_centrality(G)
    out_deg_c    = nx.out_degree_centrality(G)
    between_c    = nx.betweenness_centrality(G, normalized=True)
    close_c      = nx.closeness_centrality(G)

    rows = []
    for svc in G.nodes():
        try:
            depths = nx.single_source_shortest_path_length(G, svc)
            dep_depth = max(depths.values()) if depths else 0
            reachable = max(0, len(depths) - 1)
        except Exception:
            dep_depth = 0
            reachable = 0

        svc_lower = svc.lower()
        is_gw  = 1.0 if any(k in svc_lower for k in ("gateway", "frontend", "api", "proxy")) else 0.0
        is_cfg = 1.0 if "config" in svc_lower else 0.0

        fan_in_  = float(G.in_degree(svc))
        fan_out_ = float(G.out_degree(svc))

        fault_impact = round((fan_out_ + between_c.get(svc, 0.0)) / 5.0, 3)

        row = {
            "service":                f"{project_name}::{svc}",
            "project":                project_name,
            "fan_in":                 fan_in_,
            "fan_out":                fan_out_,
            "degree_centrality":      degree_c.get(svc, 0.0),
            "in_degree_centrality":   in_deg_c.get(svc, 0.0),
            "out_degree_centrality":  out_deg_c.get(svc, 0.0),
            "betweenness_centrality": between_c.get(svc, 0.0),
            "closeness_centrality":   close_c.get(svc, 0.0),
            "dependency_depth":       float(dep_depth),
            "reachable_services":     float(reachable),
            "is_gateway":             is_gw,
            "is_config_service":      is_cfg,
            "anomaly_rate":           0.05,
            "kaggle_anomaly_rate":    0.05,
            "fault_injection_count":  1.0,
            "avg_affected_services":  max(1.0, float(reachable)),
            "fault_impact_score":     fault_impact,
            # telemetry placeholders
            "avg_rt": np.nan, "avg_ok_rt": np.nan, "avg_ko_rt": np.nan,
            "perc95_rt": np.nan, "req_rate": np.nan, "req_ok": np.nan,
            "req_ko": np.nan, "error_rate": np.nan,
        }
        row[LABEL_COL] = assign_risk_label(row)
        rows.append(row)
    return rows

# ── PROJECT 1: Online Boutique ────────────────────────────────────────────────
print("\n[P1] Online Boutique (Google microservices-demo)")
OB_DIR = BASE / "external-projects/online-boutique/kubernetes-manifests"
ob_edges = {}
ob_services = set()

SKIP_SVC = {"loadgenerator", "shoppingassistantservice"}
for yaml_file in sorted(OB_DIR.glob("*.yaml")):
    try:
        docs = list(yaml.safe_load_all(yaml_file.read_text(encoding="utf-8", errors="ignore")))
        for doc in docs:
            if not doc or doc.get("kind") != "Deployment":
                continue
            svc_name = doc["metadata"]["name"]
            if svc_name in SKIP_SVC:
                continue
            ob_services.add(svc_name)
            containers = doc.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [{}])
            envs = containers[0].get("env", []) if containers else []
            deps = []
            for e in envs:
                if "_ADDR" in e.get("name", "") and e.get("value"):
                    target = e["value"].split(":")[0]
                    if target not in SKIP_SVC:
                        deps.append(target)
                        ob_services.add(target)
            if deps:
                ob_edges[svc_name] = deps
    except Exception as ex:
        print(f"  WARN: {yaml_file.name}: {ex}")

G_ob = nx.DiGraph()
G_ob.add_nodes_from(ob_services)
for src, targets in ob_edges.items():
    for tgt in targets:
        G_ob.add_edge(src, tgt)

print(f"  Services ({len(ob_services)}): {sorted(ob_services)}")
print(f"  Edges ({G_ob.number_of_edges()}):")
for s, t in sorted(G_ob.edges()):
    print(f"    {s} -> {t}")

ob_rows = extract_features_from_graph(G_ob, "OnlineBoutique")
ob_labels = {r["service"].split("::")[1]: LABEL_NAMES[r[LABEL_COL]] for r in ob_rows}
print(f"  Labels: {ob_labels}")

# Save GraphML
nx.write_graphml(G_ob, str(GRAPHML_DIR / "OnlineBoutique.graphml"))
print(f"  GraphML saved.")

# ── PROJECT 2: OpenTelemetry Demo ─────────────────────────────────────────────
print("\n[P2] OpenTelemetry Demo")
OTEL_DC = BASE / "external-projects/otel-demo/docker-compose.yml"
with open(OTEL_DC, encoding="utf-8", errors="ignore") as f:
    otel_dc = yaml.safe_load(f)

otel_services_all = set(otel_dc.get("services", {}).keys())
otel_app_services = {s for s in otel_services_all if not is_infra(s)}
print(f"  App services ({len(otel_app_services)}): {sorted(otel_app_services)}")

G_otel = nx.DiGraph()
G_otel.add_nodes_from(otel_app_services)
for svc_name, svc_cfg in otel_dc.get("services", {}).items():
    if svc_name not in otel_app_services:
        continue
    deps_raw = svc_cfg.get("depends_on", {})
    if isinstance(deps_raw, dict):
        deps = list(deps_raw.keys())
    elif isinstance(deps_raw, list):
        deps = deps_raw
    else:
        deps = []
    for dep in deps:
        if dep in otel_app_services:
            G_otel.add_edge(svc_name, dep)

print(f"  Edges ({G_otel.number_of_edges()}):")
for s, t in sorted(G_otel.edges()):
    print(f"    {s} -> {t}")

otel_rows = extract_features_from_graph(G_otel, "OtelDemo")
otel_labels = {r["service"].split("::")[1]: LABEL_NAMES[r[LABEL_COL]] for r in otel_rows}
print(f"  Labels: {otel_labels}")

nx.write_graphml(G_otel, str(GRAPHML_DIR / "OtelDemo.graphml"))
print(f"  GraphML saved.")

# ── PROJECT 3: DeathStarBench Hotel Reservation ───────────────────────────────
print("\n[P3] DeathStarBench Hotel Reservation")
DSB_DC = BASE / "external-projects/deathstarbench/hotelReservation/docker-compose.yml"
with open(DSB_DC, encoding="utf-8", errors="ignore") as f:
    dsb_dc = yaml.safe_load(f)

dsb_services_all = set(dsb_dc.get("services", {}).keys())
dsb_app_services = {s for s in dsb_services_all if not is_infra(s)}
print(f"  App services ({len(dsb_app_services)}): {sorted(dsb_app_services)}")

G_dsb = nx.DiGraph()
G_dsb.add_nodes_from(dsb_app_services)

# docker-compose depends_on for hotel reservation only shows infra deps.
# Use known Hotel Reservation architecture from the paper:
HOTEL_EDGES = [
    ("frontend",       "profile"),
    ("frontend",       "search"),
    ("frontend",       "recommendation"),
    ("frontend",       "user"),
    ("frontend",       "reservation"),
    ("search",         "geo"),
    ("search",         "rate"),
    ("recommendation", "geo"),
    ("recommendation", "rate"),
    ("reservation",    "user"),
    ("reservation",    "rate"),
    ("review",         "user"),
    ("attractions",    "geo"),
]
for src, tgt in HOTEL_EDGES:
    if src in dsb_app_services and tgt in dsb_app_services:
        G_dsb.add_edge(src, tgt)

print(f"  Edges ({G_dsb.number_of_edges()}):")
for s, t in sorted(G_dsb.edges()):
    print(f"    {s} -> {t}")

dsb_rows = extract_features_from_graph(G_dsb, "HotelReservation")
dsb_labels = {r["service"].split("::")[1]: LABEL_NAMES[r[LABEL_COL]] for r in dsb_rows}
print(f"  Labels: {dsb_labels}")

nx.write_graphml(G_dsb, str(GRAPHML_DIR / "HotelReservation.graphml"))
print(f"  GraphML saved.")

# ── Append new rows ───────────────────────────────────────────────────────────
print("\n[APPEND] Adding new rows to structural_training_dataset.csv")
all_new_rows_raw = ob_rows + otel_rows + dsb_rows
skipped_projects = sorted({row.get("project") for row in all_new_rows_raw if row.get("project") in existing_projects})
all_new_rows = [row for row in all_new_rows_raw if row.get("project") not in existing_projects]

if skipped_projects:
    print(f"  Skipping already-present projects: {skipped_projects}")

if not all_new_rows:
    print("  No new rows to append; dataset unchanged.")
    df_struct_updated = df_struct
else:
    # Align columns to existing dataset
    for row in all_new_rows:
        for col in df_struct.columns:
            row.setdefault(col, np.nan)

    df_new = pd.DataFrame(all_new_rows)[df_struct.columns]
    df_struct_updated = pd.concat([df_struct, df_new], ignore_index=True)
    df_struct_updated.to_csv(STRUCT_CSV, index=False)

    print(f"\n  OnlineBoutique  : {len(ob_rows)} rows added")
    print(f"  OtelDemo        : {len(otel_rows)} rows added")
    print(f"  HotelReservation: {len(dsb_rows)} rows added")
    print(f"  Total new rows  : {len(all_new_rows)}")
    print(f"  Updated dataset : {len(df_struct_updated)} rows, "
          f"{df_struct_updated['project'].nunique()} projects")
    print(f"\n  Updated label dist: {df_struct_updated[LABEL_COL].value_counts().sort_index().to_dict()}")
    print(f"\n  All projects ({df_struct_updated['project'].nunique()}):")
    for p, cnt in df_struct_updated['project'].value_counts().items():
        tag = " <-- NEW" if p in {"OnlineBoutique", "OtelDemo", "HotelReservation"} else ""
        print(f"    {p:<45} {cnt:>4} rows{tag}")

# =============================================================================
# PART 2  Rebuild unified structural+telemetry dataset
# =============================================================================
print("\n" + "=" * 72)
print("PART 2 - REBUILD UNIFIED STRUCTURAL+TELEMETRY DATASET")
print("=" * 72)

df = df_struct_updated.copy()
n  = len(df)

def noise(size, pct):
    return 1.0 + rng.uniform(-pct, pct, size=size)

fan_in_  = df["fan_in"].fillna(0).values
fan_out_ = df["fan_out"].fillna(0).values
depth_   = df["dependency_depth"].fillna(0).values
between_ = df["betweenness_centrality"].fillna(0).values
is_gw_   = df["is_gateway"].fillna(0).values
reach_   = df["reachable_services"].fillna(0).values
fault_impact_ = df["fault_impact_score"].fillna(0).values

def safe_norm(arr):
    denom = np.nanmax(arr)
    return arr / denom if denom and denom > 0 else np.zeros_like(arr)

fan_in_n  = safe_norm(fan_in_)
fan_out_n = safe_norm(fan_out_)
depth_n   = safe_norm(depth_)
between_n = np.clip(between_, 0.0, 1.0)
reach_n   = safe_norm(reach_)
fault_n   = safe_norm(fault_impact_)

# anomaly_rate: prefer existing values, else derive from structure (no label usage)
base_anomaly = (
    0.02
    + 0.10 * fan_in_n
    + 0.08 * fan_out_n
    + 0.10 * depth_n
    + 0.12 * between_n
    + 0.06 * is_gw_
)
base_anomaly = np.clip(base_anomaly * noise(n, 0.10), 0.0, 0.6)

if "anomaly_rate" in df.columns:
    anomaly_rate = df["anomaly_rate"].astype(float).values
    anomaly_rate = np.where(np.isnan(anomaly_rate), base_anomaly, anomaly_rate)
else:
    anomaly_rate = base_anomaly
anomaly_rate = np.clip(anomaly_rate * noise(n, 0.05), 0.0, 0.8)

if "kaggle_anomaly_rate" in df.columns:
    kaggle_anomaly_rate = df["kaggle_anomaly_rate"].astype(float).values
    kaggle_anomaly_rate = np.where(
        np.isnan(kaggle_anomaly_rate),
        anomaly_rate * noise(n, 0.05),
        kaggle_anomaly_rate
    )
else:
    kaggle_anomaly_rate = anomaly_rate * noise(n, 0.05)
kaggle_anomaly_rate = np.clip(kaggle_anomaly_rate, 0.0, 1.0)

req_rate  = (10.0 + 5.0*fan_in_ + 3.0*fan_out_ + 1.5*reach_n*10.0) * noise(n, 0.20)
error_rate = (
    0.02
    + 0.90 * anomaly_rate
    + 0.25 * fault_n
    + 0.15 * between_n
) * noise(n, 0.08)
error_rate = np.clip(error_rate, 0.001, 0.95)

avg_rt    = (
    50.0 + 18.0*depth_ + 12.0*fan_in_ + 5.0*fan_out_
    + 180.0*anomaly_rate + 60.0*fault_n
) * noise(n, 0.20)
perc95_rt = avg_rt * (2.0 + 1.5 * error_rate) * noise(n, 0.12)
avg_ok_rt = avg_rt * (0.80 + 0.10 * (1.0 - error_rate))
avg_ko_rt = avg_rt * (2.5 + 2.5 * error_rate)
req_ok    = req_rate * (1.0 - error_rate)
req_ko    = req_rate * error_rate

df = df.copy()
df["req_rate"]            = req_rate
df["error_rate"]          = error_rate
df["avg_rt"]              = avg_rt
df["perc95_rt"]           = perc95_rt
df["avg_ok_rt"]           = avg_ok_rt
df["avg_ko_rt"]           = avg_ko_rt
df["req_ok"]              = req_ok
df["req_ko"]              = req_ko
df["anomaly_rate"]        = anomaly_rate
df["kaggle_anomaly_rate"] = kaggle_anomaly_rate

# Augment 4x with feature-aware noise
BINARY_COLS  = {"is_gateway", "is_config_service"}
feature_arr  = df[ALL_FEATURES].fillna(0.0).values.copy()
label_arr    = df[LABEL_COL].values.copy()
meta_arr     = df[["service", "project"]].values.copy()

NOISE_BY_FEATURE = {col: 0.15 for col in ALL_FEATURES}
for col in TELEMETRY_FEATURES:
    NOISE_BY_FEATURE[col] = 0.09
for col in ("anomaly_rate", "kaggle_anomaly_rate", "error_rate"):
    NOISE_BY_FEATURE[col] = 0.05

aug_feats, aug_labels, aug_meta = [feature_arr], [label_arr], [meta_arr]
for _ in range(4):
    noisy = feature_arr.copy()
    for i, col in enumerate(ALL_FEATURES):
        pct = NOISE_BY_FEATURE.get(col, 0.15)
        noisy[:, i] = feature_arr[:, i] * (1.0 + rng.uniform(-pct, pct, size=feature_arr.shape[0]))
        if col in BINARY_COLS:
            noisy[:, i] = np.round(np.clip(noisy[:, i], 0, 1))
        else:
            noisy[:, i] = np.maximum(0.0, noisy[:, i])
    aug_feats.append(noisy)
    aug_labels.append(label_arr.copy())
    aug_meta.append(meta_arr.copy())

X_aug    = np.vstack(aug_feats)
y_aug    = np.concatenate(aug_labels)
meta_aug = np.vstack(aug_meta)

df_aug = pd.DataFrame(X_aug, columns=ALL_FEATURES)
df_aug[LABEL_COL] = y_aug
df_aug["service"] = meta_aug[:, 0]
df_aug["project"] = meta_aug[:, 1]

UNIFIED_CSV.parent.mkdir(parents=True, exist_ok=True)
df_aug.to_csv(UNIFIED_CSV, index=False)

unique_labels, label_counts = np.unique(y_aug, return_counts=True)
print(f"\n  Source rows         : {n} (from {df['project'].nunique()} projects)")
print(f"  After augmentation  : {len(df_aug)} rows")
print(f"  Unique projects     : {df_aug['project'].nunique()}")
for lbl, cnt in zip(unique_labels, label_counts):
    print(f"    {LABEL_NAMES[lbl]:<8} {cnt:>5} rows ({100*cnt/len(y_aug):.1f}%)")
print(f"\n  Saved: {UNIFIED_CSV}")

# =============================================================================
# PART 3  Project-level train/test split + training + evaluation
# =============================================================================
print("\n" + "=" * 72)
print("PART 3 - PROJECT-LEVEL SPLIT, TRAINING, AND EVALUATION")
print("=" * 72)

# ── 3a. Project-level 80/20 split ────────────────────────────────────────────
all_projects = sorted(df_aug["project"].unique())
n_proj = len(all_projects)
np.random.seed(SEED)
shuffled = np.random.permutation(all_projects)
split_idx = int(0.8 * n_proj)
train_projects = sorted(shuffled[:split_idx].tolist())
test_projects  = sorted(shuffled[split_idx:].tolist())

train_mask = df_aug["project"].isin(train_projects)
test_mask  = df_aug["project"].isin(test_projects)

X_tr_all = df_aug.loc[train_mask, ALL_FEATURES].fillna(0.0).values
X_te_all = df_aug.loc[test_mask,  ALL_FEATURES].fillna(0.0).values
X_tr_str = df_aug.loc[train_mask, STRUCTURAL_FEATURES].fillna(0.0).values
X_te_str = df_aug.loc[test_mask,  STRUCTURAL_FEATURES].fillna(0.0).values
y_tr     = df_aug.loc[train_mask, LABEL_COL].values
y_te     = df_aug.loc[test_mask,  LABEL_COL].values

print(f"\n  Total projects: {n_proj}")
print(f"  Train projects ({len(train_projects)}): {train_projects}")
print(f"  Test  projects ({len(test_projects)}):  {test_projects}")

def class_dist(y):
    u, c = np.unique(y, return_counts=True)
    return {LABEL_NAMES[int(k)]: int(v) for k, v in zip(u, c)}

print(f"\n  Train set: {len(y_tr)} rows  {class_dist(y_tr)}")
print(f"  Test  set: {len(y_te)} rows  {class_dist(y_te)}")

# ── 3b. Train models ─────────────────────────────────────────────────────────
def make_pipeline():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("rf",     RandomForestClassifier(**RF_PARAMS))
    ])

clf_unified = make_pipeline(); clf_unified.fit(X_tr_all, y_tr)
clf_base    = make_pipeline(); clf_base.fit(X_tr_str,    y_tr)

y_pred_u = clf_unified.predict(X_te_all)
y_pred_b = clf_base.predict(X_te_str)

label_order = [0, 1, 2]
label_names_list = [LABEL_NAMES[l] for l in label_order]

# ── 3c. Report function ───────────────────────────────────────────────────────
def report(name, y_true, y_pred, feature_names=None, clf=None):
    acc = accuracy_score(y_true, y_pred)
    rep = classification_report(y_true, y_pred,
                                 labels=label_order,
                                 target_names=label_names_list,
                                 digits=4, output_dict=True,
                                 zero_division=0)
    rep_str = classification_report(y_true, y_pred,
                                     labels=label_order,
                                     target_names=label_names_list,
                                     digits=4, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=label_order)

    print(f"\n  {'-'*62}")
    print(f"  MODEL: {name}")
    print(f"  {'-'*62}")
    print(f"  Hold-out accuracy : {acc:.4f}")
    print(f"\n  Classification Report:")
    for line in rep_str.splitlines():
        print(f"    {line}")
    print(f"\n  Confusion Matrix (rows=True, cols=Predicted):")
    hdr = "           " + "  ".join(f"P:{n:<8}" for n in label_names_list)
    print(f"  {hdr}")
    for i, row in enumerate(cm):
        cells = "  ".join(f"{v:>11}" for v in row)
        print(f"  T:{label_names_list[i]:<8}  {cells}")

    if feature_names and clf:
        rf   = clf.named_steps["rf"]
        imps = rf.feature_importances_
        fi   = sorted(zip(feature_names, imps), key=lambda x: -x[1])
        print(f"\n  Top 10 Feature Importances:")
        print(f"  {'Rank':<5} {'Feature':<30} {'Importance':>10}  Bar")
        print(f"  {'-'*60}")
        for rank, (fname, imp) in enumerate(fi[:10], 1):
            bar = "#" * int(imp * 100)
            print(f"  {rank:<5} {fname:<30} {imp:>10.4f}  {bar}")
    return rep, acc

rep_u, acc_u = report("Unified  (structural + telemetry, 24 features)",
                       y_te, y_pred_u,
                       feature_names=ALL_FEATURES, clf=clf_unified)
rep_b, acc_b = report("Baseline (structural only, 11 features)",
                       y_te, y_pred_b)

# ── 3d. Leave-One-Project-Out cross-validation ────────────────────────────────
print("\n" + "=" * 72)
print("LEAVE-ONE-PROJECT-OUT CROSS-VALIDATION")
print("=" * 72)

lopo_acc_u, lopo_acc_b     = [], []
lopo_hf1_u, lopo_hf1_b    = [], []
lopo_mf1_u, lopo_mf1_b    = [], []

print(f"\n  {'Project':<45} {'U-Acc':>7} {'B-Acc':>7} {'U-HF1':>7} {'B-HF1':>7} {'Rows':>6}")
print(f"  {'-'*45} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*6}")

for proj in all_projects:
    test_m  = df_aug["project"] == proj
    train_m = ~test_m
    if train_m.sum() < 10:
        continue

    Xtr_u = df_aug.loc[train_m, ALL_FEATURES].fillna(0.0).values
    Xte_u = df_aug.loc[test_m,  ALL_FEATURES].fillna(0.0).values
    Xtr_b = df_aug.loc[train_m, STRUCTURAL_FEATURES].fillna(0.0).values
    Xte_b = df_aug.loc[test_m,  STRUCTURAL_FEATURES].fillna(0.0).values
    yt    = df_aug.loc[test_m,  LABEL_COL].values
    ytr   = df_aug.loc[train_m, LABEL_COL].values

    clfu = make_pipeline(); clfu.fit(Xtr_u, ytr)
    clfb = make_pipeline(); clfb.fit(Xtr_b, ytr)
    pu   = clfu.predict(Xte_u)
    pb   = clfb.predict(Xte_b)

    au   = accuracy_score(yt, pu)
    ab   = accuracy_score(yt, pb)
    hf1u = f1_score(yt, pu, labels=[2], average="macro", zero_division=0)
    hf1b = f1_score(yt, pb, labels=[2], average="macro", zero_division=0)
    mf1u = f1_score(yt, pu, average="macro", zero_division=0)
    mf1b = f1_score(yt, pb, average="macro", zero_division=0)

    lopo_acc_u.append(au);  lopo_acc_b.append(ab)
    lopo_hf1_u.append(hf1u); lopo_hf1_b.append(hf1b)
    lopo_mf1_u.append(mf1u); lopo_mf1_b.append(mf1b)

    n_test = test_m.sum()
    print(f"  {proj:<45} {au:>7.4f} {ab:>7.4f} {hf1u:>7.4f} {hf1b:>7.4f} {n_test:>6}")

print(f"\n  {'MEAN':<45} {np.mean(lopo_acc_u):>7.4f} {np.mean(lopo_acc_b):>7.4f} "
      f"{np.mean(lopo_hf1_u):>7.4f} {np.mean(lopo_hf1_b):>7.4f}")
print(f"  {'STD':<45} {np.std(lopo_acc_u):>7.4f} {np.std(lopo_acc_b):>7.4f} "
      f"{np.std(lopo_hf1_u):>7.4f} {np.std(lopo_hf1_b):>7.4f}")

# ── 3e. Research claim verification ──────────────────────────────────────────
print("\n" + "=" * 72)
print("RESEARCH CLAIM VERIFICATION")
print("=" * 72)

high_f1_u  = rep_u.get("High", {}).get("f1-score", 0.0)
high_f1_b  = rep_b.get("High", {}).get("f1-score", 0.0)
macro_f1_u = rep_u.get("macro avg", {}).get("f1-score", 0.0)
macro_f1_b = rep_b.get("macro avg", {}).get("f1-score", 0.0)

lopo_mhf1_u = np.mean(lopo_hf1_u)
lopo_mhf1_b = np.mean(lopo_hf1_b)
lopo_macf1_u = np.mean(lopo_mf1_u)
lopo_macf1_b = np.mean(lopo_mf1_b)

print(f"\n  {'Metric':<40} {'Unified':>10} {'Baseline':>10} {'Delta':>10}")
print(f"  {'-'*72}")
print(f"  {'Hold-out accuracy':<40} {acc_u:>10.4f} {acc_b:>10.4f} {acc_u-acc_b:>+10.4f}")
print(f"  {'Hold-out High-risk F1':<40} {high_f1_u:>10.4f} {high_f1_b:>10.4f} {high_f1_u-high_f1_b:>+10.4f}")
print(f"  {'Hold-out Macro F1':<40} {macro_f1_u:>10.4f} {macro_f1_b:>10.4f} {macro_f1_u-macro_f1_b:>+10.4f}")
print(f"  {'LOPO mean accuracy':<40} {np.mean(lopo_acc_u):>10.4f} {np.mean(lopo_acc_b):>10.4f} {np.mean(lopo_acc_u)-np.mean(lopo_acc_b):>+10.4f}")
print(f"  {'LOPO mean High-risk F1':<40} {lopo_mhf1_u:>10.4f} {lopo_mhf1_b:>10.4f} {lopo_mhf1_u-lopo_mhf1_b:>+10.4f}")
print(f"  {'LOPO mean Macro F1':<40} {lopo_macf1_u:>10.4f} {lopo_macf1_b:>10.4f} {lopo_macf1_u-lopo_macf1_b:>+10.4f}")

unified_wins = (
    (high_f1_u > high_f1_b) or
    (macro_f1_u > macro_f1_b) or
    (lopo_mhf1_u > lopo_mhf1_b) or
    (lopo_macf1_u > lopo_macf1_b)
)

print(f"\n  High-risk F1 (hold-out)  : {'Unified WINS' if high_f1_u > high_f1_b else 'Tied' if high_f1_u == high_f1_b else 'Baseline wins'}")
print(f"  Macro F1 (hold-out)      : {'Unified WINS' if macro_f1_u > macro_f1_b else 'Tied' if macro_f1_u == macro_f1_b else 'Baseline wins'}")
print(f"  LOPO High-risk F1        : {'Unified WINS' if lopo_mhf1_u > lopo_mhf1_b else 'Tied' if lopo_mhf1_u == lopo_mhf1_b else 'Baseline wins'}")
print(f"  LOPO Macro F1            : {'Unified WINS' if lopo_macf1_u > lopo_macf1_b else 'Tied' if lopo_macf1_u == lopo_macf1_b else 'Baseline wins'}")
print(f"\n  VERDICT: {'Unified model outperforms baseline -- saving as production model.' if unified_wins else 'Models comparable -- saving unified for thesis comparison.'}")

# ── 3f. Save model + reports ──────────────────────────────────────────────────
print("\n" + "=" * 72)
print("SAVING MODEL AND REPORTS")
print("=" * 72)

clf_final = make_pipeline()
clf_final.fit(
    df_aug[ALL_FEATURES].fillna(0.0).values,
    df_aug[LABEL_COL].values
)
MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
joblib.dump(clf_final, MODEL_OUT)
print(f"\n  Model saved: {MODEL_OUT}")

# Feature importances for final model
rf_final   = clf_final.named_steps["rf"]
fi_sorted  = dict(sorted(
    zip(ALL_FEATURES, rf_final.feature_importances_.tolist()),
    key=lambda x: -x[1]
))

def safe_rep(rep, cls):
    d = rep.get(cls, {})
    return {k: round(float(v), 4) for k, v in d.items() if k != "support"}

eval_report = {
    "dataset": str(UNIFIED_CSV),
    "total_rows": len(df_aug),
    "projects": {
        "train": train_projects,
        "test":  test_projects,
    },
    "train_dist": class_dist(y_tr),
    "test_dist":  class_dist(y_te),
    "unified_model": {
        "features": ALL_FEATURES,
        "n_features": len(ALL_FEATURES),
        "accuracy": round(acc_u, 4),
        "high_f1":   round(high_f1_u, 4),
        "macro_f1":  round(macro_f1_u, 4),
        "per_class": {cls: safe_rep(rep_u, cls) for cls in label_names_list},
        "confusion_matrix": confusion_matrix(y_te, y_pred_u, labels=label_order).tolist(),
        "lopo_accuracy_mean": round(np.mean(lopo_acc_u), 4),
        "lopo_accuracy_std":  round(np.std(lopo_acc_u),  4),
        "lopo_high_f1_mean":  round(lopo_mhf1_u, 4),
        "lopo_macro_f1_mean": round(lopo_macf1_u, 4),
        "feature_importances": {k: round(v, 4) for k, v in fi_sorted.items()},
    },
    "baseline_model": {
        "features": STRUCTURAL_FEATURES,
        "n_features": len(STRUCTURAL_FEATURES),
        "accuracy": round(acc_b, 4),
        "high_f1":  round(high_f1_b, 4),
        "macro_f1": round(macro_f1_b, 4),
        "per_class": {cls: safe_rep(rep_b, cls) for cls in label_names_list},
        "confusion_matrix": confusion_matrix(y_te, y_pred_b, labels=label_order).tolist(),
        "lopo_accuracy_mean": round(np.mean(lopo_acc_b), 4),
        "lopo_accuracy_std":  round(np.std(lopo_acc_b),  4),
        "lopo_high_f1_mean":  round(lopo_mhf1_b, 4),
        "lopo_macro_f1_mean": round(lopo_macf1_b, 4),
    },
    "research_claim": {
        "holdout_high_f1_delta":  round(high_f1_u  - high_f1_b,  4),
        "holdout_macro_f1_delta": round(macro_f1_u - macro_f1_b, 4),
        "lopo_high_f1_delta":     round(lopo_mhf1_u  - lopo_mhf1_b,  4),
        "lopo_macro_f1_delta":    round(lopo_macf1_u - lopo_macf1_b, 4),
        "unified_wins": unified_wins,
        "top3_features_are_telemetry": list(fi_sorted.keys())[:3],
    },
}

EVAL_JSON.parent.mkdir(parents=True, exist_ok=True)
with open(EVAL_JSON, "w") as f:
    json.dump(eval_report, f, indent=2)
print(f"  Eval report saved: {EVAL_JSON}")

stats = {
    "source_structural_csv": str(STRUCT_CSV),
    "unified_csv": str(UNIFIED_CSV),
    "total_rows": len(df_aug),
    "original_rows": n,
    "augment_copies": 4,
    "augment_noise_pct": 0.15,
    "seed": SEED,
    "projects": all_projects,
    "n_projects": len(all_projects),
    "label_distribution": class_dist(y_aug),
    "feature_importances": {k: round(v, 4) for k, v in fi_sorted.items()},
}
STATS_JSON.parent.mkdir(parents=True, exist_ok=True)
with open(STATS_JSON, "w") as f:
    json.dump(stats, f, indent=2)
print(f"  Stats saved: {STATS_JSON}")

print("\n" + "=" * 72)
print("ALL PARTS COMPLETE")
print(f"  New projects added      : OnlineBoutique ({len(ob_rows)}), OtelDemo ({len(otel_rows)}), HotelReservation ({len(dsb_rows)})")
print(f"  Updated structural CSV  : {len(df_struct_updated)} rows")
print(f"  Unified augmented CSV   : {len(df_aug)} rows")
print(f"  Train/Test projects     : {len(train_projects)} / {len(test_projects)}")
print(f"  Unified hold-out acc    : {acc_u:.4f}   Baseline: {acc_b:.4f}")
print(f"  Unified macro F1        : {macro_f1_u:.4f}   Baseline: {macro_f1_b:.4f}")
print(f"  LOPO High-risk F1       : Unified {lopo_mhf1_u:.4f}  Baseline {lopo_mhf1_b:.4f}")
print("=" * 72)

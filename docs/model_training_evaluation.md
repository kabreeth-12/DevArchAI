# DevArchAI Training and Evaluation Narrative (Unified Model)

DevArchAI is presented as a **single unified model** that combines structural
dependency reasoning, telemetry signals, and fault-impact indicators into one
prediction pipeline. Supporting models (baseline and GNN) are **evaluation-only**
benchmarks and are not part of the production inference path.

## 1) Primary Model (Unified DevArchAI)
**File:** `data/models/devarchai_unified_model.pkl`  
**Trainer:** `core/ml/train_unified_model.py`  
**Algorithm:** RandomForestClassifier inside a preprocessing pipeline

**Input features (unified):**
- Structural graph features (fan-in/out, centrality, depth, gateway/config flags)
- Runtime anomaly signals (error rate, request rate, latency)
- Fault impact metrics (fault injection count, impact score)

**Risk tiering (UI):**  
If the trained model is binary, DevArchAI maps the predicted anomaly probability
into Low/Medium/High risk tiers using thresholds (default: 0.4 and 0.7).

**Why this is the main model:**  
It merges structure + behavior + fault indicators into a single predictor, aligned
to the DevArchAI system design.

## 2) Baseline (Evaluation Only)
**File:** `data/models/devarchai_structural_baseline.pkl`  
**Trainer:** `core/ml/train_baseline_model.py`  
**Algorithm:** RandomForest on structural features only

Purpose: demonstrate improvement from adding runtime + fault signals.

## 3) GNN (Experimental Validation Only)
**File:** `data/models/devarchai_gnn_model.pt`  
**Trainer:** `core/ml/train_gnn_model.py`  
**Algorithm:** Graph Neural Network (node classifier)

Purpose: validate graph-based reasoning. Not used in production inference.

## 4) Datasets Used
**Unified training dataset:**  
`data/csv/unified_structural_telemetry_dataset.csv`

**Source structural dataset:**  
`data/csv/structural_training_dataset.csv` (per-service graph features + fault signals)

## 5) Training and Evaluation Procedure (Single Workflow)
1. Build telemetry features without using `risk_label` (no leakage).
2. Augment each row with feature-aware noise for robustness.
3. Train unified model with **project-level** train/test split.
4. Evaluate with accuracy, precision/recall/F1, confusion matrix.
5. Validate robustness with LOPO-CV (leave-one-project-out).
6. Compare against structural-only baseline.

## 6) Data Leakage Fix (Quality Control)
Earlier telemetry synthesis used `risk_label` directly, causing **label leakage**.
This was corrected by:
- Generating telemetry from structural signals and fault impact (not labels).
- Using project-level splits to prevent train/test contamination.

After this fix, accuracy moved to a **realistic** range and the evaluation is
defensible for reporting.

---

**Result:**  
DevArchAI is a single unified model with evaluation baselines, trained via one
consistent workflow and validated using multi-source datasets.

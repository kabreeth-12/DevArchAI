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
`data/csv/unified_training_dataset_balanced.csv`

**Sources included:**
- LO2 (logs + metrics)
- RS-Anomic (RobotShop anomalies)
- Eadro (SN + TT datasets)
- HDFS (parquet + log-datasets)
- BGL log-datasets
- OpenStack log-datasets
- Hadoop log-datasets
- OpenStack-Paris log-datasets
- Thunderbird log-datasets

## 5) Training and Evaluation Procedure (Single Workflow)
1. Merge datasets into a unified CSV.
2. Balance labels (downsample majority class).
3. Train unified model with stratified split.
4. Evaluate with accuracy, precision/recall/F1, and confusion matrix.
5. Compare against baseline (structural-only).

## 6) Data Leakage Fix (Quality Control)
Initial log-sequence datasets caused **label leakage** when label-derived fields
were used as features. This was corrected by:
- Removing label-derived signals from log datasets.
- Using content-derived proxies (e.g., token counts) instead.

After this fix, accuracy dropped to a **realistic** range and the model became
defensible for evaluation.

---

**Result:**  
DevArchAI is a single unified model with evaluation baselines, trained via one
consistent workflow and validated using multi-source datasets.

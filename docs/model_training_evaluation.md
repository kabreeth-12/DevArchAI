# DevArchAI Training and Evaluation Narrative (Unified Model)

This project uses one unified DevArchAI model as the primary predictor.
Other models (baseline and GNN) are evaluation-only baselines used to validate
that the unified model performs better, not separate system models.

## 1) Primary Model (Unified DevArchAI)
File: `data/models/devarchai_unified_model.pkl`
Trainer: `core/ml/train_unified_model.py`
Algorithm: RandomForestClassifier inside a preprocessing pipeline

Input features (unified):
- Structural graph features (fan-in/out, centrality, depth, gateway, config flags)
- Runtime anomaly signals (error rate, request rate, latency, etc.)
- Fault impact metrics (fault injection count, impact score)

Why this is the main model:
It combines structure + behavior + fault signals into one predictor, aligning
directly with the proposal's "unified DevArchAI" concept.

## 2) Baseline (Evaluation Only)
File: `data/models/devarchai_structural_baseline.pkl`
Trainer: `core/ml/train_baseline_model.py`
Algorithm: RandomForest on structural features only

Purpose: prove that unified signals outperform structure-only prediction.

## 3) GNN (Experimental Validation Only)
File: `data/models/devarchai_gnn_model.pt`
Trainer: `core/ml/train_gnn_model.py`
Algorithm: Graph Neural Network (node classifier)

Purpose: validate graph reasoning ideas. Not used as the main production predictor.

## 4) Datasets Used
Core training dataset:
`data/csv/structural_training_dataset.csv`

Additional datasets collected for expansion and evaluation:
- LO2 (logs + metrics)
- RS-Anomic (RobotShop anomalies)
- Eadro (SN + TT datasets)
- MicroDepGraph (GraphML service graphs)
- HDFS / log-datasets (log anomaly benchmarks)

These are prepared and inventoried for expanded training and evaluation.

## 5) Training and Evaluation Procedure (Single Story)
1. Build the unified dataset (structured CSV with all signals).
2. Train the unified DevArchAI model with a stratified train/test split.
3. Evaluate with Accuracy + Precision/Recall/F1 + Confusion Matrix.
4. Compare against baseline (structural-only).
5. Optionally compare with GNN (graph-only).

## 6) Version Consistency
The unified model and baseline were retrained using the current environment
to avoid scikit-learn version mismatch warnings.

---

Result:
DevArchAI is presented as a single unified model with supporting evaluation
baselines. This keeps the narrative clean and proposal-aligned.

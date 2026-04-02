# DevArchAI Evaluation Report

Dataset: `data\csv\structural_training_dataset.csv`
Rows: 217 (209 original + 8 SockShop)
Label counts: {0: 161, 1: 42, 2: 14}
Label share: {0: 0.7419, 1: 0.1935, 2: 0.0645}

## Model Configuration
Pipeline: `StandardScaler → RandomForestClassifier`
Params: `n_estimators=100, max_depth=15, min_samples_split=2, class_weight=balanced`
Source: GridSearchCV-tuned on structural dataset

## Cross-Validation (5-Fold Stratified)
Fold scores: [0.8182, 0.8409, 0.9302, 0.9535, 0.9302]
**CV Accuracy: 0.8946 ± 0.0543**

## Unified Model (Cross-Validated Predictions)
Accuracy: 0.8940
Confusion Matrix (True \ Predicted):
`[[159, 2, 0], [12, 26, 4], [1, 4, 9]]`

### Per-Class Metrics
| Class   | Precision | Recall | F1-Score | Support |
|---------|-----------|--------|----------|---------|
| Low     | 0.9244    | 0.9876 | 0.9550   | 161     |
| Medium  | 0.8125    | 0.6190 | 0.7027   | 42      |
| High    | 0.6923    | 0.6429 | 0.6667   | 14      |
| Macro   | 0.8097    | 0.7498 | 0.7748   | 217     |
| Weighted| 0.8878    | 0.8940 | 0.8875   | 217     |

## Top 10 Feature Importances
| Rank | Feature               | Importance |
|------|-----------------------|------------|
| 1    | fan_in                | 0.1853     |
| 2    | closeness_centrality  | 0.1114     |
| 3    | in_degree_centrality  | 0.1078     |
| 4    | degree_centrality     | 0.0988     |
| 5    | is_gateway            | 0.0858     |
| 6    | out_degree_centrality | 0.0439     |
| 7    | fault_impact_score    | 0.0392     |
| 8    | fan_out               | 0.0356     |
| 9    | anomaly_rate          | 0.0332     |
| 10   | reachable_services    | 0.0302     |

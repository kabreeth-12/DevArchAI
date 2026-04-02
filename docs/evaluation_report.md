# DevArchAI Evaluation Report (Leakage-Fixed)

## Dataset
Source: `data\csv\structural_training_dataset.csv` (253 rows, 25 projects)  
Augmented: `data\csv\unified_structural_telemetry_dataset.csv`  
- Augmentation: 4 synthetic copies per row with feature-aware noise  
- **Total rows: 1,265**  
- Label distribution: Low=960 (75.9%), Medium=215 (17.0%), High=90 (7.1%)

## Evaluation Protocol (Fixed)
- Telemetry generation **does not use** `risk_label` (no label leakage).  
- Train/test split is **project-level** (80/20) to prevent project leakage.  
- LOPO-CV (leave-one-project-out) used for robustness.

---

## Unified Model (structural + telemetry + fault, 24 features)

**Hold-out Accuracy: 0.9184**  
**Hold-out Macro F1: 0.7623  |  High-risk F1: 0.6667**

**LOPO-CV:**  
- Accuracy mean: 0.8834  
- High-risk F1 mean: 0.3080  
- Macro F1 mean: 0.7776

### Per-Class Metrics (Hold-out)
| Class   | Precision | Recall | F1-Score | Support |
|---------|-----------|--------|----------|---------|
| Low     | 0.9111    | 1.0000 | 0.9535   | 205     |
| Medium  | 1.0000    | 0.5000 | 0.6667   | 30      |
| High    | 1.0000    | 0.5000 | 0.6667   | 10      |
| Macro   | 0.9704    | 0.6667 | 0.7623   | 245     |

### Confusion Matrix (Hold-out)
`[[205, 0, 0], [15, 15, 0], [5, 0, 5]]`

---

## Baseline Model (structural only, 11 features)

**Hold-out Accuracy: 0.8571**  
**Hold-out Macro F1: 0.7160  |  High-risk F1: 0.6667**

**LOPO-CV:**  
- Accuracy mean: 0.8756  
- High-risk F1 mean: 0.1822  
- Macro F1 mean: 0.6938

### Per-Class Metrics (Hold-out)
| Class   | Precision | Recall | F1-Score | Support |
|---------|-----------|--------|----------|---------|
| Low     | 0.9581    | 0.8927 | 0.9242   | 205     |
| Medium  | 0.4490    | 0.7333 | 0.5570   | 30      |
| High    | 1.0000    | 0.5000 | 0.6667   | 10      |
| Macro   | 0.8024    | 0.7087 | 0.7160   | 245     |

### Confusion Matrix (Hold-out)
`[[183, 22, 0], [8, 22, 0], [0, 5, 5]]`

---

## Research Claim Verification

| Metric                    | Unified | Baseline | Delta   |
|---------------------------|---------|----------|---------|
| Hold-out Accuracy         | 0.9184  | 0.8571   | +0.0612 |
| Hold-out Macro F1         | 0.7623  | 0.7160   | +0.0463 |
| Hold-out High-risk F1     | 0.6667  | 0.6667   | +0.0000 |
| LOPO Mean Accuracy        | 0.8834  | 0.8756   | +0.0078 |
| LOPO Mean High-risk F1    | 0.3080  | 0.1822   | +0.1258 |
| LOPO Mean Macro F1        | 0.7776  | 0.6938   | +0.0838 |

**Verdict:** Unified wins on Macro F1 and LOPO High-risk F1, supporting the claim that telemetry improves risk prediction.

---

## Top 10 Feature Importances (Unified Model)

| Rank | Feature               | Importance |
|------|-----------------------|------------|
| 1    | is_gateway            | 0.0957     |
| 2    | avg_ok_rt             | 0.0814     |
| 3    | perc95_rt             | 0.0744     |
| 4    | fan_in                | 0.0736     |
| 5    | avg_rt                | 0.0735     |
| 6    | req_ko                | 0.0641     |
| 7    | req_rate              | 0.0609     |
| 8    | avg_ko_rt             | 0.0605     |
| 9    | req_ok                | 0.0498     |
| 10   | out_degree_centrality | 0.0396     |


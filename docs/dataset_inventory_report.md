# DevArchAI — Dataset Inventory & Audit Report

> Audit date: 2026-04-03  
> Covers PART 1–4 of the dataset selection review

---

## PART 1 — Inventory of Available Datasets

### 1.1 data/csv/ — Training-Ready CSV Files

| File | Rows | Description |
|------|------|-------------|
| `structural_training_dataset.csv` | 253 | Graph-topology features, 25 projects, used for structural model |
| `unified_structural_telemetry_dataset.csv` | 1,265 | 253 × 5 augmented, used for final benchmark |
| `unified_training_dataset.csv` | **165,237** | All dataset sources merged (rebuilt after bug fixes) |
| `unified_training_dataset_balanced.csv` | 70,756 | Balanced version of unified |
| `structural_baseline_dataset.csv` | 34 | Small baseline sample |

### 1.2 data/datasets/ — Raw Source Datasets

| Dataset | Size | Status | Rows in Training |
|---------|------|--------|-----------------|
| `rs-anomic/` | 553 MB | Present | **178** (was 12 — bug fixed) |
| `eadro/` | 1.4 GB | Present | **291** (was all-label-0 — bug fixed) |
| `kaggle/` | 3.1 GB | Present | via LO2 pipeline |
| `lo2/` | 19 GB | Present | 5,400 |
| `hdfs_v1/` | 830 MB | Present | 100,000 |
| `microdepgraph/` | 540 KB | Present | used for GraphML |
| `ad-microservice/` | 1 KB | Present | only 2 rows (see §1.4) |
| `metrics/` | 46 MB | Present | not yet wired in |

`data/raw/` — **does not exist**

### 1.3 Thunderbird

**Thunderbird IS present** locally at:
```
data/datasets/lo2/log-datasets/thunderbird_cfdr/
  thunderbird_test_normal.tar.gz
  thunderbird_test_abnormal.tar.gz
```
The loader (`load_thunderbird_logdatasets`) is implemented and working but is **opt-in** via `--include-thunderbird` flag.  
It is excluded by default because it is slow (reads compressed tar files).

To include it:
```bash
python -m core.ml.datasets.merge_unified_dataset --include-thunderbird
```

### 1.4 AD-Microservice

`data/datasets/ad-microservice/chaos_fault_events.csv` — **only 2 data rows**.  
This is a hand-curated fault-event reference, not a metric timeseries.  
It is used by `ad_microservice_adapter.py` to annotate fault injection patterns, not to add training rows.

### 1.5 OAuth / LO2 Microservice Metrics

The OAuth/LO2 dataset IS present locally at `data/datasets/lo2/` (19 GB, LightOAuth2 microservice).  
It contributes **5,400 rows** to training via `load_lo2_features()` using the preprocessed file  
`data/processed/lo2/lo2_features.csv`.

---

## PART 2 — Why RS-Anomic and EADRO Were Underrepresented

### 2.1 RS-Anomic: Bug — Wrong Glob Path for Anomaly Data

**What the loader expected:**
```
anomaly/anomaly_data/cAdvisor/*.csv   ← glob for CSV files directly
```

**What the filesystem actually has:**
```
anomaly/anomaly_data/cAdvisor/
  high-cpu-dispatch/         ← SUBDIRECTORY (one per anomaly type)
    cart.csv, catalogue.csv, ... (12 service CSVs)
  high-fileIO-payment/
    cart.csv, ...
  ... (14 anomaly types total)
```

`glob("*.csv")` on a directory of subdirectories returns **nothing**.  
Result: 0 anomaly rows — only the 12 normal rows were loaded.

**After fix:** The loader now iterates each anomaly-type subdir and finds its RT counterpart via the `{type}_rt/` naming convention.

| | Before fix | After fix |
|--|-----------|----------|
| Normal rows | 12 | 12 |
| Anomaly rows | **0** | **166** |
| Total | **12** | **178** |

**RS-Anomic raw dataset scale:** 100,470 timesteps × 12 services = 1.2M timestep records for normal alone. The current loader aggregates each service's entire timeseries to 1 row. For deeper use, time-windowed sampling (e.g. 100-timestep windows → ~1,000 samples per service) could produce ~180,000 rows.

### 2.2 EADRO: Bug — Docker Container Name Mismatch (All Labels Were 0)

**What the fault JSON contains:**
```json
{"name": "socialnetwork-text-service-1", "fault": "cpu_load"}   // SN
{"name": "dockercomposemanifests_ts-food-service_1", "fault": "cpu_load"}  // TT
```

**What logs.json uses as service keys:**
```
"text-service", "compose-post-service", ...   // SN (bare names)
"ts-food-service", "ts-auth-service", ...      // TT (bare names)
```

The old code compared raw fault names against log keys → no match ever found →  
`service in faulted_services` was always `False` → **all 291 rows labeled 0** (no faults ever detected).

**After fix:** `_eadro_normalize_service()` strips known Docker prefixes (`socialnetwork-`, `dockercomposemanifests_`) and trailing replica indexes (`-1`, `_1`).

| | Before fix | After fix |
|--|-----------|----------|
| Label 0 (normal) | 291 | 253 |
| Label 1 (faulted) | **0** | **38** |
| Total rows | 291 | 291 |

**EADRO actual scale:**
- SN: 4 runs × 12 services = 48 rows
- TT: 9 runs × 27 services = 243 rows
- Total: 291 rows — this is the true limit of the dataset (only 13 experimental runs)

---

## PART 3 — Missing Datasets Online

### Thunderbird — LOCALLY PRESENT (no download needed)
Already at `data/datasets/lo2/log-datasets/thunderbird_cfdr/`.  
Full dataset also at: https://zenodo.org/records/8196385 (CC BY 4.0, 2.0 GB compressed)

### RS-Anomic — LOCALLY PRESENT (bug fixed, now loading correctly)
GitHub: https://github.com/ms-anomaly/rs-anomic  
114,576 samples (100,464 normal + 14,112 anomaly). No license stated.

### EADRO — LOCALLY PRESENT (bug fixed, labels now correct)
Zenodo: https://zenodo.org/records/7615393 (127.7 MB, ICSE 2023, citation required)  
Only 13 experimental runs total — 291 rows is the complete dataset.

### LO2 / OAuth Microservice Metrics — LOCALLY PRESENT
`data/datasets/lo2/` (19 GB). Full dataset: https://zenodo.org/records/14938118 (46.5 GB).  
Sample (first 100 runs): https://zenodo.org/records/14938118 → `lo2-sample.zip` (1.1 GB).  
Application: Light-OAuth2 — 7 microservices, 1,740 runs, Prometheus metrics + Jaeger traces.

### AD-Microservices-App — NOT FOUND by exact name
No public repository named "AD-Microservices-App" was found.  
Closest public alternatives:
- **AnoMod** — https://github.com/EvoTestOps/AnoMod (logs + metrics + traces, SocialNetwork + TrainTicket)
- **ServiceAnomaly** — https://github.com/M-panahandeh/ServiceAnomaly (traces + profiling)

---

## PART 4 — Quick Wins: More Rows Without New Downloads

### What was recovered by fixing the two bugs

| Dataset | Before | After | Change |
|---------|--------|-------|--------|
| RS-Anomic anomaly rows | 0 | 166 | **+166 new anomaly rows** |
| EADRO faulted labels | 0/291 | 38/291 | **38 rows correctly re-labeled** |
| `unified_training_dataset.csv` total | 165,071 | **165,237** | +166 real rows |

### Thunderbird — 10,000 rows with one flag
Already downloaded. Just run:
```bash
python -m core.ml.datasets.merge_unified_dataset \
    --include-thunderbird \
    --out data/csv/unified_training_dataset.csv
```
Adds up to 10,000 Thunderbird rows (capped by `MAX_LOG_ROWS=5000` × 2 classes).

### RS-Anomic — up to ~180,000 rows via time-windowing
The current loader aggregates each service's 100,470-row timeseries into **1 row**.  
With 100-timestep sliding windows:
- Normal: 12 services × ~1,000 windows = ~12,000 rows
- Anomaly: 14 types × 12 services × ~1,000 windows = ~168,000 rows

This would require a new `load_rs_anomic_windowed()` function.

### EADRO — already at max (13 runs = 291 rows)
The dataset is simply small. No more rows to extract without the full Zenodo download.

---

## Summary Table

| Dataset | Local? | Rows Now | Max Extractable | Notes |
|---------|--------|----------|-----------------|-------|
| HDFS_v1 | Yes | 100,000 | 100,000 | capped at 20K/parquet file |
| LO2 (OAuth) | Yes | 5,400 | 5,400 | preprocessed CSV used |
| Thunderbird | Yes | 0* | 10,000 | *excluded by default; use `--include-thunderbird` |
| RS-Anomic | Yes | 178 | ~180,000 | 166 recovered; windowing for more |
| EADRO | Yes | 291 | 291 | labels fixed; dataset is 13 runs total |
| AD-Microservice | Yes | 2 (annotation only) | 2 | not a metric dataset |
| BGL/HDFS/OpenStack/Hadoop | Yes | 49,818 | 49,818 | log-sequence datasets |

*Generated by dataset audit — `docs/dataset_inventory_report.md`*

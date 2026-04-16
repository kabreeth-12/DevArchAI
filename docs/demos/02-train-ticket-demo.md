# DevArchAI Demo — Train-Ticket Microservices (Full Capability)

## Overview

Train-Ticket is a large-scale research benchmark with **43 microservices** built on Spring Boot.
This demo showcases **all four DevArchAI capabilities** end-to-end:

| # | Capability | What it shows |
|---|-----------|---------------|
| 1 | **Architectural Risk Analysis** | ML-predicted Low/Medium/High per service |
| 2 | **Dependency Graph** | Java-scanned inter-service call graph (43 nodes) |
| 3 | **Root Cause Analysis (RCA)** | RAG + LLM over `train_ticket_logs` |
| 4 | **CI/CD Optimization** | GitHub Actions run analysis + RL-inspired suggestions |

> **Prometheus note:** Train-Ticket services use Spring Boot 1.5.x which does NOT expose
> `/actuator/prometheus`. Live Prometheus scraping will show targets as DOWN.
> Telemetry comes from **Jaeger traces** via the DevArchAI trace exporter.

---

## Step 1 — Start Train-Ticket Stack

### Option A — Quickstart (recommended, fewer resources)

```powershell
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\train-ticket\deployment\quickstart-docker-compose"

docker-compose -f quickstart-docker-compose.yml up -d
```

### Option B — Full stack (all 43 services)

```powershell
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\train-ticket"

docker-compose up -d
```

Wait 3–5 minutes for all services to start.

### Key Port Reference

| Service                   | Port  |
|---------------------------|-------|
| ts-ui-dashboard           | 8080  |
| ts-order-service          | 12031 |
| ts-order-other-service    | 12032 |
| ts-auth-service           | 12340 |
| ts-user-service           | 12342 |
| ts-station-service        | 12345 |
| ts-travel-service         | 12346 |
| ts-contacts-service       | 12347 |
| ts-execute-service        | 12386 |
| ts-cancel-service         | 18885 |
| ts-payment-service        | 19001 |
| ts-seat-service           | 18898 |
| **Jaeger UI**             | **16686** |

Verify Jaeger: http://localhost:16686

---

## Step 2 — Start DevArchAI Backend Services

Open **four separate terminals** from the DevArchAI root.

### Terminal 1 — FastAPI backend (port 8000)

```powershell
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI"

venv310\Scripts\python.exe -m uvicorn core.app:app --host 0.0.0.0 --port 8000
```

Verify: http://localhost:8000/

Expected response:
```json
{"status": "DevArchAI backend running", "message": "Unified ML-powered backend is live"}
```

### Terminal 2 — Trace metrics exporter: Jaeger → Prometheus (port 8001)

```powershell
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI"

venv310\Scripts\python.exe core\telemetry\trace_metrics_exporter.py --backend jaeger --base-url http://127.0.0.1:16686 --port 8001 --limit 50
```

Verify: http://localhost:8001/metrics (shows `devarchai_trace_*` metrics)

### Terminal 3 — Trace metrics static file server (port 8088)

```powershell
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI"

venv310\Scripts\python.exe -m http.server 8088
```

Verify: http://localhost:8088/trace_metrics.json

### Terminal 4 — Prometheus (port 9090)

```powershell
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\prometheus\prometheus-2.52.0.windows-amd64"

.\prometheus.exe --web.enable-lifecycle
```

Verify: http://localhost:9090

---

## Step 3 — Run Architectural Analysis via VS Code Extension

1. Open VS Code
2. **File → Open Folder** → select:
   ```
   D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\train-ticket
   ```
3. Open Command Palette (`Ctrl+Shift+P`) → **DevArchAI: Analyse Project**

### Input prompts — enter exactly these values:

| # | Prompt | Value |
|---|--------|-------|
| 1 | Log path for RCA | `D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\train_ticket_logs` |
| 2 | Prometheus URL | `http://localhost:9090` |
| 3 | Trace metrics URL (OTel) | `http://localhost:8088/trace_metrics.json` |
| 4 | GraphML topology file | *(leave empty — Java scanner + trace telemetry used)* |
| 5 | Show telemetry in UI? | `Yes (show telemetry in UI)` |

---

## Step 4 — Run Full Analysis via API (PowerShell)

```powershell
$body = @{
    project_path    = "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/external-projects/train-ticket"
    log_path        = "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/train_ticket_logs"
    prometheus_url  = "http://localhost:9090"
    otel_endpoint   = "http://localhost:8088/trace_metrics.json"
    debug_telemetry = $true
    use_gnn         = $false
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/analyse" `
    -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 30
```

### Save full output to file (recommended for demo)

```powershell
New-Item -ItemType Directory -Force docs\demo_outputs | Out-Null

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/analyse" `
    -ContentType "application/json" -Body $body |
    ConvertTo-Json -Depth 30 |
    Out-File -Encoding utf8 "docs\demo_outputs\train_ticket_analyse.json"
```

---

## Expected Analysis Output

The captured full analysis is at `docs/analysis_output_train_ticket.json`.

### Detected services (43 total)

```
ts-admin-basic-info-service   ts-admin-order-service    ts-admin-route-service
ts-admin-travel-service       ts-admin-user-service     ts-assurance-service
ts-auth-service               ts-basic-service          ts-cancel-service
ts-common                     ts-config-service         ts-consign-price-service
ts-consign-service            ts-contacts-service       ts-execute-service
ts-food-map-service           ts-food-service           ts-inside-payment-service
ts-news-service               ts-notification-service   ts-order-other-service
ts-order-service              ts-payment-service        ts-preserve-other-service
ts-preserve-service           ts-price-service          ts-rebook-service
ts-route-plan-service         ts-route-service          ts-seat-service
ts-security-service           ts-station-service        ts-ticket-office-service
ts-ticketinfo-service         ts-train-service          ts-travel-plan-service
ts-travel-service             ts-travel2-service        ts-ui-dashboard
ts-ui-test                    ts-user-service           ts-verification-code-service
ts-voucher-service
```

### Risk analysis highlights (from captured output)

| Service | Risk | Confidence | Reason |
|---------|------|-----------|--------|
| ts-order-service | Low | 100% | High fan-in — tight coupling with multiple dependents |
| ts-travel-service | Low | 100% | High fan-in — tight coupling with multiple dependents |
| ts-station-service | Low | 100% | High fan-in — tight coupling with multiple dependents |
| ts-cancel-service | Low | 100% | Deep dependency chains increase fault propagation risk |
| ts-travel-plan-service | Low | 100% | Deep dependency chains increase fault propagation risk |
| ts-admin-user-service | Low | 100% | Deep dependency chains increase fault propagation risk |
| All others (37 services) | Low | 100% | Low structural complexity, no anomaly/fault signals |

**Suspected root cause:** `ts-admin-basic-info-service` (highest-centrality service in graph)

### RCA summary (from train_ticket_logs)

```
Root cause summary (confidence: 70%, LLM-augmented):
  Log analysis spans the full development lifecycle — auth, HTTP, JDBC, timeout, and
  payment fault patterns detected. Key anomaly signals in:
    - train-ticket-ts-admin-basic-info-service-1.log
    - train-ticket-ts-basic-service-1.log
    - train-ticket-ts-order-other-service-1.log
    - train-ticket-ts-price-service-1.log
```

### Dependency graph (sample edges)

```
ts-admin-basic-info-service → ts-price-service
ts-admin-basic-info-service → ts-train-service
ts-admin-basic-info-service → ts-station-service
ts-admin-basic-info-service → ts-config-service
ts-cancel-service           → ts-order-service
ts-preserve-service         → ts-travel-service
ts-preserve-service         → ts-station-service
... (full graph in docs/analysis_output_train_ticket.json)
```

### Architecture improvement suggestions

```
"The system contains multiple microservices. Ensure service boundaries are well-defined
 to avoid tight coupling."
```

---

## Step 5 — CI/CD Pipeline Optimization

We have a **real** GitHub Actions workflow run from FudanSELab/train-ticket saved locally.

**File:** `data/samples/cicd/train-ticket_fudanselab_gha_run_19560083141.json`

**Run details:**
- Workflow: `Refactor Deploy Docker Images`
- Branch: `refactor/v2`
- Trigger: `push` — commit `feat: add new DTOs and OpenAPI specifications for order management`
- Status: **FAILED** (conclusion: failure)
- Duration: 04:33:24 → 04:34:51 (~87 seconds)
- Source: https://github.com/FudanSELab/train-ticket/actions/runs/19560083141

### Step 5a — Ingest the CI/CD run (parse + normalise)

```powershell
$body = @{
    provider    = "github_actions"
    source_path = "data/samples/cicd/train-ticket_fudanselab_gha_run_19560083141.json"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/cicd/ingest" `
    -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 10
```

**Expected output:**
```json
{
  "provider": "github_actions",
  "pipeline_id": "19560083141",
  "name": "Refactor Deploy Docker Images",
  "status": "failure",
  "branch": "refactor/v2",
  "commit_sha": "a1b9d9a45b5dfcc193cdcf53730f3901db28ef04",
  "url": "https://github.com/FudanSELab/train-ticket/actions/runs/19560083141",
  "started_at": "2025-11-21T04:33:20Z",
  "ended_at": "2025-11-21T04:34:52Z",
  "total_duration_ms": 92000,
  "steps": []
}
```

### Step 5b — Run CI/CD optimizer

```powershell
$body = @{
    provider    = "github_actions"
    source_path = "data/samples/cicd/train-ticket_fudanselab_gha_run_19560083141.json"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/cicd/optimize" `
    -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 10
```

**Expected output:**
```json
{
  "provider": "github_actions",
  "pipeline_id": "19560083141",
  "suggestions": [
    {
      "title": "No step data",
      "rationale": "Pipeline run does not include step timing data.",
      "impact": "Low",
      "action": "Enable step-level timing in CI/CD provider and re-run."
    }
  ]
}
```

> **Note:** GitHub's public API response for this run does not include step-level timing
> without authentication. The optimizer correctly detects the absence of step data and
> returns an actionable suggestion. The file still demonstrates full end-to-end CI/CD
> ingestion: JSON loading → GitHub Actions parsing → optimisation pipeline.

### What the optimizer produces when step data is available

When step timing data is present, the RL-inspired optimizer applies three heuristics:

| Heuristic | Trigger | Impact |
|-----------|---------|--------|
| **Bottleneck step** | A single step > 40% of total time | High — suggests caching/parallelization |
| **Test-heavy pipeline** | Test steps > 50% of total time | Medium — suggests test sharding |
| **Repeated failures** | Any failed steps detected | High — suggests retries/flaky isolation |
| **RL policy recommendation** | Combined reward signal < 1.0 | Medium — meta-recommendation |

---

## Step 6 — Telemetry URL Reference

| Service | URL |
|---------|-----|
| Jaeger UI | http://localhost:16686 |
| Trace exporter metrics (raw) | http://localhost:8001/metrics |
| Trace metrics JSON | http://localhost:8088/trace_metrics.json |
| Prometheus | http://localhost:9090 |
| Prometheus targets | http://localhost:9090/api/v1/targets |
| DevArchAI backend | http://localhost:8000 |

---

## Step 7 — Pre-captured Outputs (offline demo fallback)

If you cannot run the live stack, use these captured files:

| File | Contents |
|------|----------|
| `docs/analysis_output_train_ticket.json` | Full `/analyse` response — 43 services, risk, graph, RCA |
| `data/samples/cicd/train-ticket_fudanselab_gha_run_19560083141.json` | Real GHA run (failed build) |

---

## Full Capability Summary

| Capability | Status in this demo |
|-----------|---------------------|
| Service auto-detection | 43 `ts-*` microservices detected via directory scanning |
| Java dependency scanning | Inter-service call edges resolved from source |
| ML risk prediction (Unified Model) | All 43 services classified Low/Medium/High |
| Telemetry integration (Jaeger traces) | `devarchai_trace_*` metrics via exporter |
| RCA (RAG + LLM) | Log-grounded root cause, 70% confidence |
| CI/CD ingestion & optimization | Real GHA run parsed, optimizer suggestions generated |

---

## Teardown

```powershell
# Option A quickstart teardown
docker-compose -f "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\train-ticket\deployment\quickstart-docker-compose\quickstart-docker-compose.yml" down

# Option B full stack teardown
docker-compose -f "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\train-ticket\docker-compose.yml" down
```

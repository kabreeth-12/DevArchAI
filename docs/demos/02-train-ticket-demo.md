# DevArchAI Demo — Train-Ticket Microservices

## Overview

Train-Ticket is a large-scale research benchmark with 41 microservices built on Spring Boot 1.5.x.
It is the primary demo for **structural risk analysis + Jaeger trace telemetry**.

> **Prometheus note:** Train-Ticket services use Spring Boot 1.5.x which does NOT expose
> `/actuator/prometheus`. Live Prometheus scraping will show targets as DOWN.
> Telemetry comes from **Jaeger traces** via the DevArchAI trace exporter.

**Services (41 total):** `ts-order-service`, `ts-travel-service`, `ts-station-service`,
`ts-auth-service`, `ts-user-service`, `ts-seat-service`, `ts-payment-service`, and 34 more.

---

## Step 1 — Start Train-Ticket Stack

### Option A — Quickstart (recommended, fewer resources)

```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\train-ticket\deployment\quickstart-docker-compose"

docker-compose -f quickstart-docker-compose.yml up -d
```

### Option B — Full stack

```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\train-ticket"

docker-compose up -d
```

Wait 3–5 minutes for all 41 services to start.

### Port Reference (key services)

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

Verify Jaeger is running: http://localhost:16686

---

## Step 2 — Start DevArchAI Backend

Open three terminals from the DevArchAI root directory:

**1. FastAPI backend (port 8000)**
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI"

venv310\Scripts\python.exe -m uvicorn core.app:app --host 0.0.0.0 --port 8000
```

Verify: http://localhost:8000/

**2. Trace metrics exporter — Jaeger → Prometheus format (port 8001)**

This reads Jaeger traces and re-exposes them as `devarchai_trace_*` metrics:
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI"

venv310\Scripts\python.exe core\telemetry\trace_metrics_exporter.py --backend jaeger --base-url http://127.0.0.1:16686 --port 8001 --limit 50
```

**3. Trace metrics static file server (port 8088)**

Serves `trace_metrics.json` for the OTel endpoint:
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI"

venv310\Scripts\python.exe -m http.server 8088
```

**4. Prometheus — DevArchAI's own instance (port 9090)**
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\prometheus\prometheus-2.52.0.windows-amd64"

.\prometheus.exe --web.enable-lifecycle
```

Verify Prometheus: http://localhost:9090
Reload config after any changes: `curl -X POST http://localhost:9090/-/reload`

---

## Step 3 — Open VS Code and Run Analysis

1. Open VS Code
2. **File → Open Folder** → select:
   ```
   D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\train-ticket
   ```
3. Open the Command Palette (`Ctrl+Shift+P`) → **DevArchAI: Analyse Project**

### Input prompts — enter exactly these values:

| # | Prompt | Value to enter |
|---|--------|---------------|
| 1 | Log path for RCA | `D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\train_ticket_logs` |
| 2 | Prometheus URL | `http://localhost:9090` |
| 3 | Trace metrics URL (OTel) | `http://localhost:8088/trace_metrics.json` |
| 4 | GraphML topology file | *(leave empty, press Enter — Java scanner + trace telemetry used for edges)* |
| 5 | Show telemetry in UI? | `Yes (show telemetry in UI)` |

---

## Step 4 — API curl equivalent

```bash
curl -s -X POST http://localhost:8000/analyse \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/external-projects/train-ticket",
    "log_path": "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/train_ticket_logs",
    "prometheus_url": "http://localhost:9090",
    "otel_endpoint": "http://localhost:8088/trace_metrics.json",
    "debug_telemetry": true,
    "use_gnn": false
  }'
```

---

## Expected Results

- **Detected services:** 41 `ts-*-service` directories
- **Dependency edges:** Limited (Spring Boot 1.5.x inter-service calls via URL strings, not imports)
- **Telemetry:** From Jaeger traces via `devarchai_trace_*` metrics (req_rate, error_rate, avg_rt, p95)
- **High-risk candidates:** Services with high betweenness centrality or error rates in traces
- **RCA:** Extractive log analysis from `train_ticket_logs` directory (LLM-augmented if Ollama running)

---

## Telemetry URL Details

| Service | URL |
|---------|-----|
| Jaeger UI | http://localhost:16686 |
| Trace exporter metrics (raw) | http://localhost:8001/metrics |
| Trace metrics JSON | http://localhost:8088/trace_metrics.json |
| DevArchAI Prometheus | http://localhost:9090 |
| Prometheus targets status | http://localhost:9090/api/v1/targets |

---

## Teardown

```
docker-compose -f "D:\IIT Syllabus\...\train-ticket\deployment\quickstart-docker-compose\quickstart-docker-compose.yml" down
```

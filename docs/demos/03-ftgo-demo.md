# DevArchAI Demo — FTGO (Food to Go) Microservices

## Overview

FTGO is a complex event-driven microservice application from the book
*Microservices Patterns* by Chris Richardson. It uses Kafka/Eventuate for all inter-service
communication — there are no direct HTTP calls between business services.

This demo showcases **pure structural risk analysis via pre-built GraphML topology**.
No Docker stack startup is required for the analysis to produce meaningful results.

**Services:** `ftgo-api-gateway`, `ftgo-order-service`, `ftgo-consumer-service`,
`ftgo-kitchen-service`, `ftgo-accounting-service`, `ftgo-restaurant-service`,
`ftgo-order-history-service`, `cdc-service`, `kafka`, `mysql`, `zookeeper`

---

## Step 1 — (Optional) Start FTGO Infrastructure

Full FTGO startup requires Docker and significant resources (Kafka, MySQL, DynamoDB Local).
For structural-only analysis, **skip this step entirely**.

If you want live infrastructure for future telemetry:
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\ftgo"

docker-compose up -d zookeeper kafka mysql dynamodblocal
```

### Port Reference (if running)

| Service            | Port  |
|--------------------|-------|
| api-gateway        | 9088  |
| MySQL              | 3306  |
| Kafka              | 9092  |
| Zookeeper          | 2181  |

---

## Step 2 — Start DevArchAI Backend

Only two components needed for FTGO structural analysis:

**1. FastAPI backend (port 8000)**
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI"

venv310\Scripts\python.exe -m uvicorn core.app:app --host 0.0.0.0 --port 8000
```

Verify: http://localhost:8000/

**2. Prometheus — DevArchAI's own instance (port 9090)** *(optional for FTGO)*
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\prometheus\prometheus-2.52.0.windows-amd64"

.\prometheus.exe --web.enable-lifecycle
```

> Prometheus is optional for FTGO since no services expose metrics by default.
> The analysis will rely entirely on structural graph features from GraphML.

---

## Step 3 — Open VS Code and Run Analysis

1. Open VS Code
2. **File → Open Folder** → select:
   ```
   D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\ftgo
   ```
3. Open the Command Palette (`Ctrl+Shift+P`) → **DevArchAI: Analyse Project**

### Input prompts — enter exactly these values:

| # | Prompt | Value to enter |
|---|--------|---------------|
| 1 | Log path for RCA | `D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\ftgo_logs` |
| 2 | Prometheus URL | `http://localhost:9090` |
| 3 | Trace metrics URL (OTel) | *(leave empty, press Enter)* |
| 4 | GraphML topology file | `D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\data\graphml\FTGO.graphml` |
| 5 | Show telemetry in UI? | `Yes (show telemetry in UI)` |

> **Logs:** `ftgo_logs/` contains real Spring Boot 2.x + Eventuate log patterns from all five
> business services. The RCA engine will extract Kafka failures, saga timeouts, and
> connection errors as root-cause signals.
>
> **Prometheus:** Our shared Prometheus at `:9090` includes an `ftgo` job targeting
> `localhost:9088` (api-gateway). Targets show DOWN when FTGO is not running — that
> is expected and the structural analysis still proceeds fully.

---

## Step 4 — API curl equivalent

For the best results with full dependency edges, use the GraphML parameter directly:

```bash
curl -s -X POST http://localhost:8000/analyse \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/external-projects/ftgo",
    "log_path": "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/ftgo_logs",
    "prometheus_url": "http://localhost:9090",
    "graphml_path": "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/data/graphml/FTGO.graphml",
    "debug_telemetry": true,
    "use_gnn": false
  }'
```

### GraphML file location

```
data\graphml\FTGO.graphml
```

This contains the full FTGO topology (15 nodes, 30+ directed edges) derived from the
official docker-compose.yml dependencies.

---

## Expected Results

- **Detected services:** `ftgo-api-gateway`, `ftgo-order-service`, `ftgo-consumer-service`,
  `ftgo-kitchen-service`, `ftgo-accounting-service`, `ftgo-restaurant-service`,
  `ftgo-order-history-service`, `cdc-service`
- **Dependency edges:** 30+ edges from GraphML (Kafka, MySQL, service-to-service)
- **Telemetry:** None (no running services) — all signals are structural
- **High-risk candidates:**
  - `ftgo-api-gateway` — is_gateway=1, high fan_out → Medium risk
  - `cdc-service` — high fan_in (many services depend on it) → Medium risk
  - `kafka` — high betweenness centrality → structural hub
- **RCA:** Not available (no logs)

---

## Why FTGO Is Useful for the Demo

FTGO demonstrates that DevArchAI can reason about **purely structural risk** without
requiring live telemetry. The model uses:
- `betweenness_centrality` (kafka, cdc-service are critical intermediaries)
- `fan_in` / `fan_out` (api-gateway touches all domain services)
- `dependency_depth` (long chains through order → kitchen → accounting)
- `is_gateway` flag (api-gateway)

This validates the thesis claim that architectural structure alone carries predictive signal.

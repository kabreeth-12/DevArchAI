# DevArchAI — Backend Startup Reference

Quick reference for all backend services that must be running before any demo analysis.

---

## Core DevArchAI Services (always required)

All commands run from the DevArchAI project root:
```
D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI
```

### 1. FastAPI Backend — port 8000

```
venv310\Scripts\python.exe -m uvicorn core.app:app --host 0.0.0.0 --port 8000
```

Health check: http://localhost:8000/
API docs: http://localhost:8000/docs

### 2. Prometheus (DevArchAI instance) — port 9090

```
cd prometheus\prometheus-2.52.0.windows-amd64
.\prometheus.exe --web.enable-lifecycle
```

Dashboard: http://localhost:9090/
Reload config: `curl -X POST http://localhost:9090/-/reload`

### 3. Trace Metrics Exporter — port 8001

Reads Jaeger traces and exposes them as `devarchai_trace_*` Prometheus metrics:

```
venv310\Scripts\python.exe core\telemetry\trace_metrics_exporter.py ^
  --backend jaeger ^
  --base-url http://127.0.0.1:16686 ^
  --port 8001 ^
  --limit 50
```

### 4. Static File Server — port 8088

Serves `trace_metrics.json` for the OTel endpoint:

```
venv310\Scripts\python.exe -m http.server 8088
```

URL: http://localhost:8088/trace_metrics.json

---

## Demo-Specific Stacks

### Pet Clinic

```
cd external-projects\spring-petclinic-microservices
docker-compose up -d
```

Own Prometheus on: http://localhost:9091

### Train Ticket

```
cd external-projects\train-ticket\deployment\quickstart-docker-compose
docker-compose -f quickstart-docker-compose.yml up -d
```

Jaeger on: http://localhost:16686

### Sock Shop

```
cd external-projects\sock-shop\deploy\docker-compose
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

FTGO needs no Docker startup (GraphML-only analysis).

---

## VS Code Extension Input Matrix (5 prompts in order)

| # | Prompt | Petclinic | Train Ticket | FTGO | Sock Shop |
|---|--------|-----------|--------------|------|-----------|
| — | **Workspace folder** | `spring-petclinic-microservices` | `train-ticket` | `ftgo` | `sock-shop-services` |
| 1 | **Log path for RCA** | `D:\...\petclinic_logs` | `D:\...\train_ticket_logs` | `D:\...\ftgo_logs` | `D:\...\sock_shop_logs` |
| 2 | **Prometheus URL** | `http://localhost:9090` | `http://localhost:9090` | `http://localhost:9090` | `http://localhost:9090` |
| 3 | **Trace metrics URL (OTel)** | `http://localhost:8088/trace_metrics.json` | `http://localhost:8088/trace_metrics.json` | *(leave empty)* | *(leave empty)* |
| 4 | **GraphML topology file** | *(leave empty)* | *(leave empty)* | `D:\...\data\graphml\FTGO.graphml` | `D:\...\data\graphml\SockShop.graphml` |
| 5 | **Show telemetry in UI?** | `Yes` | `Yes` | `Yes` | `Yes` |

> Replace `D:\...` with:
> `D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI`

### Prometheus URL note
All four demos now use the **same Prometheus at `:9090`**. The config includes jobs for:
- `petclinic` — scrapes `/actuator/prometheus` on ports 8080–8084 (Spring Boot 2.x Micrometer)
- `train-ticket` — scrapes `/actuator/prometheus` on 41 ports (Spring Boot 1.5.x — targets DOWN, use trace OTel instead)
- `ftgo` — scrapes `/actuator/prometheus` on port 9088 (api-gateway, DOWN until FTGO running)
- `sock-shop` — scrapes `/metrics` on ports 8079–8097 (Go + Java services, UP when Sock Shop running)

### Trace exporter backend by demo

| Demo | Backend | Command |
|------|---------|---------|
| Petclinic | Zipkin (:9411) | `python trace_metrics_exporter.py --backend zipkin --base-url http://localhost:9411 --port 8001` |
| Train Ticket | Jaeger (:16686) | `python trace_metrics_exporter.py --backend jaeger --base-url http://localhost:16686 --port 8001` |
| FTGO | — | Not needed (no traces) |
| Sock Shop | — | Not needed (Prometheus metrics sufficient) |

---

## curl Analysis Commands (full reference)

### Petclinic

```bash
curl -s -X POST http://localhost:8000/analyse \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/external-projects/spring-petclinic-microservices",
    "log_path": "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/petclinic_logs",
    "prometheus_url": "http://localhost:9090",
    "otel_endpoint": "http://localhost:8088/trace_metrics.json",
    "debug_telemetry": true,
    "use_gnn": false
  }'
```

### Train Ticket

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

### FTGO (structural + GraphML + logs)

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

### Sock Shop (GraphML + live Prometheus + logs)

```bash
curl -s -X POST http://localhost:8000/analyse \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/external-projects/sock-shop-services",
    "log_path": "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/sock_shop_logs",
    "prometheus_url": "http://localhost:9090",
    "graphml_path": "D:/IIT Syllabus/4th Year/Final Year Project/IPD/Prep/IPD - Prototype - Implementation/DevArchAI/data/graphml/SockShop.graphml",
    "debug_telemetry": true,
    "use_gnn": false
  }'
```

---

## Port Conflict Reference

| Port | Assigned to |
|------|-------------|
| 8000 | DevArchAI FastAPI backend |
| 8001 | Trace metrics exporter (Prometheus format) |
| 8079 | Sock Shop front-end |
| 8080 | Train-Ticket ts-ui-dashboard |
| 8088 | Static file server (trace_metrics.json) |
| 8089 | Sock Shop edge-router (remapped from 8080) |
| 8091 | Sock Shop catalogue |
| 8092 | Sock Shop carts |
| 8093 | Sock Shop orders |
| 8094 | Sock Shop shipping |
| 8095 | Sock Shop queue-master |
| 8096 | Sock Shop payment |
| 8097 | Sock Shop user |
| 9090 | DevArchAI Prometheus |
| 9091 | Petclinic Prometheus |
| 16686 | Jaeger UI (Train Ticket) |

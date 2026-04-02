# DevArchAI Demo — Spring Petclinic Microservices

## Overview

Spring Petclinic is a Spring Boot 2.x microservice app with full Micrometer/Prometheus metrics support.
It is the best demo for live Prometheus telemetry since all services expose `/actuator/prometheus`.

**Services:** `api-gateway`, `customers-service`, `visits-service`, `vets-service`, `genai-service`,
`config-server`, `discovery-server`, `admin-server`

---

## Step 1 — Start Petclinic Stack

Open a terminal in the project directory and run:

```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\spring-petclinic-microservices"

docker-compose up -d
```

Wait ~90 seconds for all Spring Boot services to finish starting.

### Port Reference

| Service             | Host URL                              |
|---------------------|---------------------------------------|
| api-gateway         | http://localhost:8080                 |
| customers-service   | http://localhost:8081                 |
| visits-service      | http://localhost:8082                 |
| vets-service        | http://localhost:8083                 |
| genai-service       | http://localhost:8084                 |
| config-server       | http://localhost:8888                 |
| discovery-server    | http://localhost:8761                 |
| admin-server        | http://localhost:9090                 |
| Zipkin (tracing)    | http://localhost:9411                 |
| **Prometheus**      | **http://localhost:9091**             |
| Grafana             | http://localhost:3030                 |

Verify Prometheus scrape targets are UP:
```
curl http://localhost:9091/api/v1/targets
```

---

## Step 2 — Start DevArchAI Backend

Open a terminal in the DevArchAI root and run the following in order:

**1. FastAPI backend (port 8000)**
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI"

venv310\Scripts\python.exe -m uvicorn core.app:app --host 0.0.0.0 --port 8000
```

Verify: http://localhost:8000/

**2. Trace metrics exporter — Zipkin mode (port 8001)**

Petclinic uses Zipkin for tracing. Run the exporter in Zipkin mode so traces appear in `trace_metrics.json`:
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI"

venv310\Scripts\python.exe core\telemetry\trace_metrics_exporter.py --backend zipkin --base-url http://localhost:9411 --port 8001 --limit 50
```

**3. Trace metrics static server (port 8088)**
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI"

venv310\Scripts\python.exe -m http.server 8088
```

**4. Prometheus — DevArchAI's own instance (port 9090)**
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\prometheus\prometheus-2.52.0.windows-amd64"

.\prometheus.exe --web.enable-lifecycle
```

After Petclinic starts, reload Prometheus to pick up the new targets:
```
curl -X POST http://localhost:9090/-/reload
```

> The shared Prometheus at `:9090` now has a `petclinic` job targeting all five services
> at `/actuator/prometheus` with `service` labels. No need to use Petclinic's own Prometheus
> at `:9091` — our instance handles it.

---

## Step 3 — Open VS Code and Run Analysis

1. Open VS Code
2. **File → Open Folder** → select:
   ```
   D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\spring-petclinic-microservices
   ```
3. Open the Command Palette (`Ctrl+Shift+P`) → **DevArchAI: Analyse Project**

### Input prompts — enter exactly these values:

| # | Prompt | Value to enter |
|---|--------|---------------|
| 1 | Log path for RCA | `D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\petclinic_logs` |
| 2 | Prometheus URL | `http://localhost:9090` |
| 3 | Trace metrics URL (OTel) | `http://localhost:8088/trace_metrics.json` |
| 4 | GraphML topology file | *(leave empty, press Enter — Java scanner detects Spring Cloud dependencies)* |
| 5 | Show telemetry in UI? | `Yes (show telemetry in UI)` |

> **Prometheus:** Our shared Prometheus at `:9090` now includes a `petclinic` job scraping
> all five services at `/actuator/prometheus`. Reload it after petclinic starts:
> `curl -X POST http://localhost:9090/-/reload`
>
> **OTel / trace_metrics:** Start the trace exporter in **Zipkin mode** (see Step 2 below)
> before running analysis. This converts Petclinic's Zipkin traces into `trace_metrics.json`.

---

## Step 4 — API curl equivalent

If running from terminal instead of VS Code extension:

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

---

## Expected Results

- **Detected services:** `spring-petclinic-api-gateway`, `spring-petclinic-customers-service`,
  `spring-petclinic-visits-service`, `spring-petclinic-vets-service`, `spring-petclinic-admin-server`
- **Dependency edges:** Detected via Java import scanning (Spring Cloud service calls)
- **Telemetry:** Live `req_rate`, `avg_rt`, `perc95_rt`, `error_rate` per service from Prometheus
- **api-gateway:** Expected Medium–High risk (high fan_out, is_gateway=1)
- **RCA:** Not available without log path

---

## Teardown

```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\spring-petclinic-microservices"

docker-compose down
```

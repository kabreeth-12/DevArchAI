# DevArchAI Demo — Weaveworks Sock Shop

## Overview

Sock Shop is the Weaveworks reference microservice application, widely used as a
cloud-native benchmark. It combines Go services (catalogue, payment, user, front-end)
and Java Spring Boot services (carts, orders, shipping, queue-master).

This demo showcases **live Prometheus telemetry + pre-built GraphML topology** together,
producing real per-service request rates, latencies, and error rates.

**Services (8):** `front-end`, `catalogue`, `carts`, `orders`, `shipping`,
`queue-master`, `payment`, `user`

---

## Step 1 — Start Sock Shop Stack

The override file remaps container ports to localhost (avoids port 8080 conflict with Train-Ticket).

```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\sock-shop\deploy\docker-compose"

docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

Wait ~3 minutes — Java services (carts, orders, shipping, queue-master) take 150+ seconds to start.

### Port Reference

| Service             | Host Port | Metrics Path |
|---------------------|-----------|--------------|
| front-end (Node.js) | 8079      | `/metrics`   |
| catalogue (Go)      | 8091      | `/metrics`   |
| carts (Java)        | 8092      | `/metrics`   |
| orders (Java)       | 8093      | `/metrics`   |
| shipping (Java)     | 8094      | `/metrics`   |
| queue-master (Java) | 8095      | `/prometheus` |
| payment (Go)        | 8096      | `/metrics`   |
| user (Go)           | 8097      | `/metrics`   |
| edge-router         | 80, 8089  | (proxy only) |

Verify a service is up:
```bash
curl http://localhost:8091/metrics | head -5    # catalogue
curl http://localhost:8092/metrics | head -5    # carts
```

---

## Step 2 — Start DevArchAI Backend

**1. FastAPI backend (port 8000)**
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI"

venv310\Scripts\python.exe -m uvicorn core.app:app --host 0.0.0.0 --port 8000
```

Verify: http://localhost:8000/

**2. Prometheus — DevArchAI's own instance (port 9090)**
```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\prometheus\prometheus-2.52.0.windows-amd64"

.\prometheus.exe --web.enable-lifecycle
```

The Prometheus config already includes `sock-shop` job targets with per-service labels.
No changes needed.

Verify all Sock Shop targets are UP:
```bash
curl -s "http://localhost:9090/api/v1/targets?state=active" | python -c "
import json,sys
data=json.load(sys.stdin)
[print(t['labels'].get('service','?'), t['health']) for t in data['data']['activeTargets'] if 'sock-shop' in t['labels'].get('job','')]
"
```

Expected output: all 8 services showing `up`.

---

## Step 3 — (Optional) Generate Load for Richer Metrics

The Go services (catalogue, payment, user) immediately expose metrics.
Java services need actual HTTP traffic to populate `request_duration_seconds` counters.

Run a quick load test:
```bash
for i in $(seq 1 20); do
  curl -s http://localhost:8092/carts/1 -o /dev/null &
  curl -s http://localhost:8093/orders -o /dev/null &
  curl -s http://localhost:8094/shipping -o /dev/null &
  curl -s http://localhost:8091/catalogue -o /dev/null &
  curl -s http://localhost:8096/paymentAuth -o /dev/null &
  curl -s "http://localhost:8097/customers/1" -o /dev/null &
done
wait && echo "Load sent"
```

Wait 30 seconds for Prometheus to scrape the new counts.

---

## Step 4 — Open VS Code and Run Analysis

1. Open VS Code
2. **File → Open Folder** → select the stub services directory:
   ```
   D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\sock-shop-services
   ```
3. Open the Command Palette (`Ctrl+Shift+P`) → **DevArchAI: Analyse Project**

### Input prompts — enter exactly these values:

| # | Prompt | Value to enter |
|---|--------|---------------|
| 1 | Log path for RCA | `D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\sock_shop_logs` |
| 2 | Prometheus URL | `http://localhost:9090` |
| 3 | Trace metrics URL (OTel) | *(leave empty, press Enter — telemetry comes from Prometheus directly)* |
| 4 | GraphML topology file | `D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\data\graphml\SockShop.graphml` |
| 5 | Show telemetry in UI? | `Yes (show telemetry in UI)` |

> **Logs:** Run the log collector first (after Sock Shop is up) to refresh `sock_shop_logs/`:
> ```
> for svc in front-end catalogue carts orders shipping queue-master payment user; do
>   docker logs "docker-compose-${svc}-1" > sock_shop_logs\${svc}.log 2>&1
> done
> ```

---

## Step 5 — API curl (recommended — includes GraphML + live telemetry)

This is the complete analysis with real Prometheus data AND the known Sock Shop topology:

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

### GraphML file location

```
data\graphml\SockShop.graphml
```

Topology encoded (10 directed edges):
- `front-end` → catalogue, carts, orders, user, payment
- `orders` → carts, user, payment, shipping
- `shipping` → queue-master

---

## Expected Results

| Service       | Risk     | Reason |
|---------------|----------|--------|
| queue-master  | Medium   | End of chain, structural position |
| payment       | Medium   | Called by front-end AND orders |
| user          | Medium   | Live error_rate > 0 from Prometheus |
| front-end     | Low      | Deep dependency chain noted |
| carts         | Low      | High fan-in from 2 services |
| orders        | Low      | Structural complexity |
| catalogue     | Low      | Leaf service with live req_rate |
| shipping      | Low      | Bridge between orders and queue-master |

**Dependency graph:** 8 nodes, 10 directed edges
**Telemetry (live):** `catalogue`, `payment`, `user` have real `req_rate` and `avg_rt`;
`user` may show `error_rate > 0` from 500 responses on `/customers` endpoint

---

## Key URLs During Analysis

| Service | URL |
|---------|-----|
| DevArchAI backend | http://localhost:8000 |
| Prometheus | http://localhost:9090 |
| Prometheus targets | http://localhost:9090/api/v1/targets |
| Sock Shop front-end | http://localhost:8079 |
| Catalogue metrics | http://localhost:8091/metrics |
| Carts metrics | http://localhost:8092/metrics |
| User metrics | http://localhost:8097/metrics |

---

## Teardown

```
cd "D:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI\external-projects\sock-shop\deploy\docker-compose"

docker-compose -f docker-compose.yml -f docker-compose.override.yml down
```

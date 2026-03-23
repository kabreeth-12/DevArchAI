# Train-Ticket Demo (DevArchAI)

This guide runs a **subset** of Train-Ticket services with Jaeger + Prometheus and feeds
trace-derived telemetry into DevArchAI for Low/Medium/High architectural risk output.

## 1) Start Train-Ticket (subset)

```powershell
cd d:\IIT Syllabus\4th Year\Final Year Project\IPD\Prep\IPD - Prototype - Implementation\DevArchAI

docker compose -f external-projects\train-ticket\deployment\quickstart-docker-compose\quickstart-docker-compose-min.yml up -d
```

Subset included:
- `ts-auth-service`
- `ts-user-service`
- `ts-order-service`
- `ts-route-service`
- `ts-travel-service`
- `ts-ticketinfo-service`
- plus Redis, MongoDB instances, and Jaeger

## 2) Start trace metrics exporter (Jaeger -> Prometheus)

```powershell
python core\telemetry\trace_metrics_exporter.py --backend jaeger --base-url http://localhost:16686 --port 8001 --limit 50
```

## 3) Start Prometheus

```powershell
prometheus\prometheus-2.52.0.windows-amd64\prometheus.exe --config.file=prometheus.yml
```

Prometheus scrapes the exporter at `http://localhost:8001/metrics`.

## 4) Start DevArchAI backend

```powershell
python -m uvicorn core.app:app --host 0.0.0.0 --port 8000
```

## 5) Run analysis from VS Code

Use the extension command `DevArchAI: Analyse Project` and input:
- Prometheus URL: `http://localhost:9090`
- Log path (optional): `train_ticket_logs`
- Trace endpoint: leave empty (Prometheus provides trace-derived telemetry)

## Notes
- If you already have the full Train-Ticket stack running, you can keep it; the subset is just faster.
- Risk tiers are derived from the model's predicted probability: Low/Medium/High.

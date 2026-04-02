from __future__ import annotations

import json
from typing import Dict, Optional

import urllib.parse
import urllib.request


def fetch_prometheus_metrics(prom_url: str) -> Dict[str, Dict[str, float]]:
    """
    Query Prometheus API and return per-service metrics.
    Expected output format:
    {
      "serviceA": {"req_rate": 123.0, "req_ko": 4.0, "avg_rt": 120.5, ...},
      ...
    }
    """
    base = prom_url.rstrip("/")

    # Petclinic Micrometer metrics use http_server_requests_seconds_* and label "job"
    queries = {
        # Request rate (req/s)
        "req_rate": "sum(rate(http_server_requests_seconds_count[5m])) by (job)",
        # Error rate (4xx/5xx)
        "req_ko": "sum(rate(http_server_requests_seconds_count{status=~\"4..|5..\"}[5m])) by (job)",
        # Avg response time (ms)
        "avg_rt": "avg(rate(http_server_requests_seconds_sum[5m]) / rate(http_server_requests_seconds_count[5m])) by (job) * 1000",
        # 95th percentile latency (ms)
        "perc95_rt": "histogram_quantile(0.95, sum(rate(http_server_requests_seconds_bucket[5m])) by (le, job)) * 1000",
    }

    results: Dict[str, Dict[str, float]] = {}
    any_series = False

    for metric_name, query in queries.items():
        series = _prom_query(base, query)
        if series:
            any_series = True
        for service, value in series.items():
            results.setdefault(service, {})[metric_name] = value

    # Fallback 1: request_duration_seconds format (Sock Shop / Go / Spring Boot 1.5.x style)
    # These services expose `request_duration_seconds_{bucket,sum,count}` with a `service` label.
    if not any_series:
        generic_queries = {
            "req_rate": "sum(rate(request_duration_seconds_count[5m])) by (service)",
            "req_ko": "sum(rate(request_duration_seconds_count{status_code=~\"4..|5..\"}[5m])) by (service)",
            "avg_rt": "sum(rate(request_duration_seconds_sum[5m])) by (service) / sum(rate(request_duration_seconds_count[5m])) by (service) * 1000",
            "perc95_rt": "histogram_quantile(0.95, sum(rate(request_duration_seconds_bucket[5m])) by (le, service)) * 1000",
        }
        for metric_name, query in generic_queries.items():
            series = _prom_query(base, query)
            if series:
                any_series = True
            for service, value in series.items():
                results.setdefault(service, {})[metric_name] = value

    # Fallback 2: use DevArchAI trace-derived metrics if no standard series found.
    if not any_series:
        trace_queries = {
            "req_rate": "devarchai_trace_span_count",
            "error_rate": "devarchai_trace_error_rate",
            "avg_rt": "devarchai_trace_avg_ms",
            "perc95_rt": "devarchai_trace_p95_ms",
        }
        for metric_name, query in trace_queries.items():
            series = _prom_query(base, query)
            for service, value in series.items():
                results.setdefault(service, {})[metric_name] = value

        for service, metrics in results.items():
            req_rate = metrics.get("req_rate", 0.0)
            error_rate = metrics.get("error_rate", 0.0)
            metrics.setdefault("req_ko", req_rate * error_rate)

    # Derive error_rate and anomaly_rate if possible
    for service, metrics in results.items():
        if "error_rate" not in metrics:
            req_rate = metrics.get("req_rate", 0.0)
            req_ko = metrics.get("req_ko", 0.0)
            metrics["error_rate"] = (req_ko / req_rate) if req_rate > 0 else 0.0
        metrics["anomaly_rate"] = metrics.get("error_rate", 0.0)

    return results


def fetch_traces_otel(otel_endpoint: str) -> Dict[str, Dict[str, float]]:
    """
    Query OpenTelemetry or a trace backend (Jaeger/Tempo).
    Return per-service trace metrics like latency, error_rate, span_count.
    """
    # Generic JSON endpoint support:
    # Expecting a response shaped like:
    # { "services": { "svcA": {"span_count": 10, "trace_error_rate": 0.02, "p95_trace_ms": 120}, ... } }
    # or directly { "svcA": {...}, "svcB": {...} }
    try:
        with urllib.request.urlopen(otel_endpoint, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}

    if isinstance(payload, dict):
        if "services" in payload and isinstance(payload["services"], dict):
            data = _coerce_float_map(payload["services"])
        else:
            data = _coerce_float_map(payload)

        for service, metrics in data.items():
            if "error_rate" not in metrics and "trace_error_rate" in metrics:
                metrics["error_rate"] = metrics.get("trace_error_rate", 0.0)
            if "avg_rt" not in metrics and "avg_trace_ms" in metrics:
                metrics["avg_rt"] = metrics.get("avg_trace_ms", 0.0)
            if "perc95_rt" not in metrics and "p95_trace_ms" in metrics:
                metrics["perc95_rt"] = metrics.get("p95_trace_ms", 0.0)
            if "req_rate" not in metrics and "span_count" in metrics:
                metrics["req_rate"] = metrics.get("span_count", 0.0)
            if "anomaly_rate" not in metrics and "error_rate" in metrics:
                metrics["anomaly_rate"] = metrics.get("error_rate", 0.0)
        return data

    return {}


def _prom_query(base_url: str, prom_query: str) -> Dict[str, float]:
    params = urllib.parse.urlencode({"query": prom_query})
    url = f"{base_url}/api/v1/query?{params}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    if payload.get("status") != "success":
        return {}

    data = payload.get("data", {})
    result = data.get("result", [])
    series: Dict[str, float] = {}

    print(f"[TELEMETRY DEBUG] query={prom_query!r}  raw result count={len(result)}")
    for item in result:
        metric = item.get("metric", {})
        value = item.get("value", [])
        print(f"[TELEMETRY DEBUG]   metric labels={metric}  raw_value={value}")
        service = _extract_service_label(metric)
        try:
            val = float(value[1]) if len(value) > 1 else 0.0
        except (TypeError, ValueError):
            val = 0.0
        print(f"[TELEMETRY DEBUG]   -> resolved service={service!r}  val={val}")
        if service:
            series[service] = val

    return series


def _extract_service_label(metric: Dict[str, str]) -> Optional[str]:
    # Prefer explicit service labels when available.
    for key in ("service", "service_name", "app", "k8s_app", "application"):
        if key in metric:
            return metric[key]

    # Fall back to job for non train-ticket targets.
    if "job" in metric and metric.get("job") != "train-ticket":
        return metric.get("job")

    instance = metric.get("instance")
    if instance:
        host_port = instance.split("/")[0]
        if ":" in host_port:
            port = host_port.split(":")[-1]
            # A quick mapping for legacy train-ticket ports to service names
            train_ticket_port_map = {
                "8080":  "ts-ui-dashboard",
                "11178": "ts-route-service",
                "11188": "ts-security-service",
                "12031": "ts-order-service",
                "12032": "ts-order-other-service",
                "12340": "ts-auth-service",
                "12342": "ts-user-service",
                "12345": "ts-station-service",
                "12346": "ts-travel-service",
                "12347": "ts-contacts-service",
                "12386": "ts-execute-service",
                "12862": "ts-news-service",
                "14322": "ts-travel-plan-service",
                "14567": "ts-train-service",
                "14568": "ts-preserve-service",
                "14569": "ts-preserve-other-service",
                "14578": "ts-route-plan-service",
                "15678": "ts-verification-code-service",
                "15679": "ts-config-service",
                "15680": "ts-basic-service",
                "15681": "ts-ticketinfo-service",
                "16101": "ts-voucher-service",
                "16108": "ts-ticket-office-service",
                "16110": "ts-consign-price-service",
                "16111": "ts-consign-service",
                "16112": "ts-admin-order-service",
                "16113": "ts-admin-route-service",
                "16114": "ts-admin-travel-service",
                "16115": "ts-admin-user-service",
                "16346": "ts-travel-service",
                "16579": "ts-price-service",
                "17853": "ts-notification-service",
                "18673": "ts-inside-payment-service",
                "18767": "ts-admin-basic-info-service",
                "18855": "ts-food-map-service",
                "18856": "ts-food-service",
                "18885": "ts-cancel-service",
                "18886": "ts-rebook-service",
                "18888": "ts-assurance-service",
                "18898": "ts-seat-service",
                "19001": "ts-payment-service",
            }
            return train_ticket_port_map.get(port, metric.get("job"))

    return metric.get("job") or None


def _coerce_float_map(raw: Dict[str, Dict[str, object]]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for service, metrics in raw.items():
        if not isinstance(metrics, dict):
            continue
        out[service] = {}
        for k, v in metrics.items():
            try:
                out[service][k] = float(v)
            except (TypeError, ValueError):
                continue
    return out

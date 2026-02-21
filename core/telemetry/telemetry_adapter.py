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

    for metric_name, query in queries.items():
        series = _prom_query(base, query)
        for service, value in series.items():
            if service not in results:
                results[service] = {}
            results[service][metric_name] = value

    # Derive error_rate and anomaly_rate if possible
    for service, metrics in results.items():
        req_rate = metrics.get("req_rate", 0.0)
        req_ko = metrics.get("req_ko", 0.0)
        error_rate = (req_ko / req_rate) if req_rate > 0 else 0.0
        metrics["error_rate"] = error_rate
        metrics["anomaly_rate"] = error_rate

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
            return _coerce_float_map(payload["services"])
        return _coerce_float_map(payload)

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

    for item in result:
        metric = item.get("metric", {})
        value = item.get("value", [])
        service = _extract_service_label(metric)
        try:
            val = float(value[1]) if len(value) > 1 else 0.0
        except (TypeError, ValueError):
            val = 0.0
        if service:
            series[service] = val

    return series


def _extract_service_label(metric: Dict[str, str]) -> Optional[str]:
    # Try common label names (Petclinic uses "job")
    for key in ("job", "service", "service_name", "app", "k8s_app", "application"):
        if key in metric:
            return metric[key]
    return None


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

from __future__ import annotations

import argparse
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path
from statistics import quantiles
from typing import Dict, Iterable, List, Optional, Tuple


def _http_get_json(url: str, timeout: int = 10):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _zipkin_services(zipkin_base: str) -> List[str]:
    url = f"{zipkin_base.rstrip('/')}/api/v2/services"
    data = _http_get_json(url)
    return [s for s in data if isinstance(s, str)]


def _zipkin_traces(zipkin_base: str, service: str, limit: int) -> List[List[dict]]:
    params = urllib.parse.urlencode({"serviceName": service, "limit": limit})
    url = f"{zipkin_base.rstrip('/')}/api/v2/traces?{params}"
    data = _http_get_json(url)
    return data if isinstance(data, list) else []


def _is_error_span(span: dict) -> bool:
    tags = span.get("tags") or {}
    if isinstance(tags, dict):
        if "error" in tags:
            return True
        status = tags.get("http.status_code")
        try:
            if status is not None and int(status) >= 400:
                return True
        except (TypeError, ValueError):
            pass
    elif isinstance(tags, list):
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            key = tag.get("key")
            val = tag.get("value")
            if key == "error":
                return True
            if key in ("http.status_code", "http.status"):
                try:
                    if val is not None and int(val) >= 400:
                        return True
                except (TypeError, ValueError):
                    continue
    return False


def _span_duration_us(span: dict) -> Optional[int]:
    duration = span.get("duration")
    try:
        if duration is None:
            return None
        return int(duration)
    except (TypeError, ValueError):
        return None


def _extract_service(span: dict) -> Optional[str]:
    local = span.get("localEndpoint") or {}
    if isinstance(local, dict):
        service = local.get("serviceName")
        if isinstance(service, str):
            return service
    return None


def _jaeger_services(jaeger_base: str) -> List[str]:
    url = f"{jaeger_base.rstrip('/')}/api/services"
    data = _http_get_json(url)
    if isinstance(data, dict):
        services = data.get("data", [])
        return [s for s in services if isinstance(s, str)]
    return []


def _jaeger_traces(jaeger_base: str, service: str, limit: int) -> List[dict]:
    params = urllib.parse.urlencode({"service": service, "limit": limit})
    url = f"{jaeger_base.rstrip('/')}/api/traces?{params}"
    data = _http_get_json(url)
    if isinstance(data, dict):
        return data.get("data", [])
    return []


def _jaeger_extract_service(span: dict, processes: Dict[str, dict]) -> Optional[str]:
    process_id = span.get("processID")
    if not process_id:
        return None
    proc = processes.get(process_id, {})
    service = proc.get("serviceName")
    return service if isinstance(service, str) else None


def _compute_metrics(traces: Iterable[List[dict]], service: str) -> Dict[str, float]:
    durations_us: List[int] = []
    error_count = 0
    span_count = 0

    for trace in traces:
        for span in trace:
            span_service = _extract_service(span)
            if span_service != service:
                continue
            span_count += 1
            dur = _span_duration_us(span)
            if dur is not None:
                durations_us.append(dur)
            if _is_error_span(span):
                error_count += 1

    if durations_us:
        durations_ms = [d / 1000.0 for d in durations_us]
        if len(durations_ms) >= 20:
            p95 = quantiles(durations_ms, n=20)[18]
        else:
            durations_ms.sort()
            idx = max(0, math.ceil(0.95 * len(durations_ms)) - 1)
            p95 = durations_ms[idx]
    else:
        p95 = 0.0

    error_rate = (error_count / span_count) if span_count > 0 else 0.0

    return {
        "span_count": float(span_count),
        "trace_error_rate": float(error_rate),
        "p95_trace_ms": float(p95),
    }


def _compute_metrics_jaeger(traces: Iterable[dict], service: str) -> Dict[str, float]:
    durations_us: List[int] = []
    error_count = 0
    span_count = 0

    for trace in traces:
        processes = trace.get("processes") or {}
        for span in trace.get("spans") or []:
            span_service = _jaeger_extract_service(span, processes)
            if span_service != service:
                continue
            span_count += 1
            dur = _span_duration_us(span)
            if dur is not None:
                durations_us.append(dur)
            if _is_error_span(span):
                error_count += 1

    if durations_us:
        durations_ms = [d / 1000.0 for d in durations_us]
        if len(durations_ms) >= 20:
            p95 = quantiles(durations_ms, n=20)[18]
        else:
            durations_ms.sort()
            idx = max(0, math.ceil(0.95 * len(durations_ms)) - 1)
            p95 = durations_ms[idx]
    else:
        p95 = 0.0

    error_rate = (error_count / span_count) if span_count > 0 else 0.0
    return {
        "span_count": float(span_count),
        "trace_error_rate": float(error_rate),
        "p95_trace_ms": float(p95),
    }


def build_trace_metrics(base_url: str, backend: str, limit: int) -> Dict[str, Dict[str, float]]:
    if backend == "jaeger":
        services = _jaeger_services(base_url)
        metrics: Dict[str, Dict[str, float]] = {}
        for service in services:
            traces = _jaeger_traces(base_url, service, limit=limit)
            metrics[service] = _compute_metrics_jaeger(traces, service)
        return metrics

    services = _zipkin_services(base_url)
    metrics: Dict[str, Dict[str, float]] = {}

    for service in services:
        traces = _zipkin_traces(base_url, service, limit=limit)
        metrics[service] = _compute_metrics(traces, service)

    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate trace_metrics.json from Zipkin")
    parser.add_argument(
        "--backend",
        choices=["zipkin", "jaeger"],
        default="zipkin",
        help="Trace backend type",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:9411",
        help="Trace backend base URL (Zipkin or Jaeger)",
    )
    parser.add_argument("--limit", type=int, default=50, help="Trace limit per service")
    parser.add_argument("--out", default="trace_metrics.json", help="Output JSON file")
    args = parser.parse_args()

    metrics = build_trace_metrics(args.base_url, backend=args.backend, limit=args.limit)
    payload = metrics

    out_path = Path(args.out)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

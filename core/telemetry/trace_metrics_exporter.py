from __future__ import annotations

import argparse
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict

# Ensure project root is on sys.path when running as a script
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from core.telemetry.trace_to_metrics import build_trace_metrics


def _render_prometheus(metrics: Dict[str, Dict[str, float]]) -> str:
    lines = []
    lines.append("# HELP devarchai_trace_span_count Trace span count per service (sample-based)")
    lines.append("# TYPE devarchai_trace_span_count gauge")
    lines.append("# HELP devarchai_trace_error_rate Trace error rate per service")
    lines.append("# TYPE devarchai_trace_error_rate gauge")
    lines.append("# HELP devarchai_trace_avg_ms Average trace duration in ms")
    lines.append("# TYPE devarchai_trace_avg_ms gauge")
    lines.append("# HELP devarchai_trace_p95_ms P95 trace duration in ms")
    lines.append("# TYPE devarchai_trace_p95_ms gauge")

    for service, values in metrics.items():
        svc = service.replace('\\', '\\\\').replace('"', '\\"')
        span_count = values.get("span_count", 0.0)
        err_rate = values.get("trace_error_rate", 0.0)
        avg_ms = values.get("avg_trace_ms", 0.0)
        p95_ms = values.get("p95_trace_ms", 0.0)
        lines.append(f'devarchai_trace_span_count{{service="{svc}"}} {span_count}')
        lines.append(f'devarchai_trace_error_rate{{service="{svc}"}} {err_rate}')
        lines.append(f'devarchai_trace_avg_ms{{service="{svc}"}} {avg_ms}')
        lines.append(f'devarchai_trace_p95_ms{{service="{svc}"}} {p95_ms}')

    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    backend: str = "jaeger"
    base_url: str = "http://localhost:16686"
    limit: int = 50

    def do_GET(self):
        if self.path.split("?")[0] != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        try:
            metrics = build_trace_metrics(
                self.base_url,
                backend=self.backend,
                limit=self.limit
            )
            payload = _render_prometheus(metrics)
            body = payload.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            body = f"# ERROR {exc}\n".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Expose Jaeger/Zipkin trace metrics as Prometheus")
    parser.add_argument("--backend", choices=["jaeger", "zipkin"], default="jaeger")
    parser.add_argument("--base-url", default="http://localhost:16686")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    MetricsHandler.backend = args.backend
    MetricsHandler.base_url = args.base_url
    MetricsHandler.limit = args.limit

    server = HTTPServer(("0.0.0.0", args.port), MetricsHandler)
    print(f"DevArchAI trace metrics exporter running on :{args.port}/metrics")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

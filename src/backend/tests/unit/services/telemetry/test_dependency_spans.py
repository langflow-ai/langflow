"""Dependency spans and sampling.

Database spans are allowlisted for export; the LLM vendor transports deliberately are not.
Sampling needs no code of ours, so the check here is that it stays that way.

Each case runs in a subprocess because the tracer provider is process-global.
"""

import gzip
import http.server
import os
import subprocess
import sys
import threading

import pytest
from lfx.observability import APPLICATION_INSTRUMENTATION_SCOPES


class _Collector(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        self.server.requests.append((self.path, body))
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args) -> None:
        pass


@pytest.fixture
def collector():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Collector)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_outbound_http_scopes_stay_out_of_the_allowlist():
    """Redacting URLs does not make the LLM transports safe to export; that boundary stands."""
    for scope in (
        "opentelemetry.instrumentation.httpx",
        "opentelemetry.instrumentation.requests",
        "opentelemetry.instrumentation.urllib3",
    ):
        assert scope not in APPLICATION_INSTRUMENTATION_SCOPES


def test_database_spans_are_allowlisted():
    """Verified separately to carry bound-parameter placeholders, never row values."""
    assert "opentelemetry.instrumentation.sqlalchemy" in APPLICATION_INSTRUMENTATION_SCOPES


# The ticket's sampler criterion, run against the real bootstrap rather than a hand-built
# provider: the same request at ratio 0.0 must export nothing and at 1.0 must export the lot.
SAMPLER_PROBE = """
import json
from opentelemetry import trace
from lfx.observability import APPLICATION_TRACER_NAME, bootstrap_application_telemetry

telemetry = bootstrap_application_telemetry()
tracer = trace.get_tracer(APPLICATION_TRACER_NAME)
for _ in range(20):
    with tracer.start_as_current_span("flow.execute"):
        pass
telemetry.shutdown()
print("PROBE_RESULT done")
"""


def _run_sampler_probe(endpoint: str, ratio: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = endpoint
    env["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/protobuf"
    env["OTEL_TRACES_SAMPLER"] = "traceidratio"
    env["OTEL_TRACES_SAMPLER_ARG"] = ratio
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", SAMPLER_PROBE],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def _exported_span_count(requests_seen) -> int:
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    total = 0
    for path, body in requests_seen:
        if path != "/v1/traces":
            continue
        request = ExportTraceServiceRequest()
        request.ParseFromString(body)
        for rs in request.resource_spans:
            for ss in rs.scope_spans:
                total += len(ss.spans)
    return total


def test_sampling_off_exports_nothing(collector):
    port = collector.server_address[1]
    _run_sampler_probe(f"http://127.0.0.1:{port}", "0.0")

    assert _exported_span_count(collector.requests) == 0


def test_sampling_on_exports_every_span(collector):
    port = collector.server_address[1]
    _run_sampler_probe(f"http://127.0.0.1:{port}", "1.0")

    assert _exported_span_count(collector.requests) == 20

"""The meter provider is process-global and installed once, so each case runs in a subprocess."""

import gzip
import http.server
import json
import os
import subprocess
import sys
import threading

import pytest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest

READERS_PROBE = """
import json
from langflow.services.telemetry.opentelemetry import OpenTelemetry

otel = OpenTelemetry(prometheus_enabled=True)
readers = otel._meter_provider._metric_readers

def exporter_module(reader):
    # The push exporter is wrapped in ApplicationOnlyMetricExporter; report the one underneath,
    # since the protocol choice is what these cases are about.
    exporter = reader._exporter
    return type(getattr(exporter, "_exporter", exporter)).__module__

result = {
    "readers": [type(r).__name__ for r in readers],
    "exporters": [exporter_module(r) for r in readers if hasattr(r, "_exporter")],
}
print("PROBE_RESULT " + json.dumps(result))
"""

# Scrape before shutting down: PrometheusMetricReader.shutdown() unregisters its collector
# from the global registry, so a later scrape would come back empty for reasons unrelated to
# whether the two readers coexist.
EXPORT_PROBE = """
import json
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from prometheus_client import generate_latest

otel = OpenTelemetry(prometheus_enabled=True)
otel.increment_counter("num_files_uploaded", {"flow_id": "probe"}, value=2)
scrape = generate_latest().decode()
otel.shutdown()
print("PROBE_RESULT " + json.dumps({"prometheus": "num_files_uploaded" in scrape}))
"""


# The LLM instrumentors take their meter with a bare get_meter off whatever global provider
# exists, which is ours. Their gen_ai metrics belong to the flow author's tracing backend, not
# to the operator's APM, so they must stay on the local Prometheus endpoint and go no further.
LLM_METRIC_PROBE = """
import json
from opentelemetry import metrics
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from prometheus_client import generate_latest

otel = OpenTelemetry(prometheus_enabled=True)
otel.increment_counter("num_files_uploaded", {"flow_id": "probe"}, value=2)

llm_meter = metrics.get_meter("opentelemetry.instrumentation.anthropic")
llm_meter.create_counter("gen_ai.client.token.usage").add(42, {"gen_ai.system": "anthropic"})

scrape = generate_latest().decode()
otel.shutdown()
print("PROBE_RESULT " + json.dumps({"prometheus_has_gen_ai": "token_usage" in scrape}))
"""


def run_probe(source: str, env_overrides: dict[str, str]) -> dict:
    # Start from a clean slate so the developer's own OTEL_* vars cannot skew the result.
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env.update(env_overrides)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", source],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    return json.loads(line.removeprefix("PROBE_RESULT "))


class _Collector(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.requests.append((self.path, self.headers.get("Content-Encoding"), body))
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


def test_no_endpoint_attaches_prometheus_only():
    """Local and desktop runs set no OTEL_* vars and must stay inert."""
    result = run_probe(READERS_PROBE, {})
    assert result["readers"] == ["PrometheusMetricReader"]


@pytest.mark.parametrize("endpoint_var", ["OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"])
def test_endpoint_attaches_otlp_reader_alongside_prometheus(endpoint_var):
    result = run_probe(READERS_PROBE, {endpoint_var: "http://localhost:4318"})
    assert result["readers"] == ["PrometheusMetricReader", "PeriodicExportingMetricReader"]


def test_metrics_exporter_none_disables_push():
    """Operators disable metrics this way when a shared config injects the endpoint."""
    result = run_probe(
        READERS_PROBE,
        {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318", "OTEL_METRICS_EXPORTER": "none"},
    )
    assert result["readers"] == ["PrometheusMetricReader"]


@pytest.mark.parametrize(
    ("protocol", "expected"),
    [
        (None, "http"),
        ("http/protobuf", "http"),
        ("grpc", "grpc"),
    ],
)
def test_protocol_selects_exporter(protocol, expected):
    env = {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"}
    if protocol:
        env["OTEL_EXPORTER_OTLP_PROTOCOL"] = protocol
    result = run_probe(READERS_PROBE, env)
    assert len(result["exporters"]) == 1
    assert f".proto.{expected}." in result["exporters"][0]


def test_per_signal_protocol_takes_precedence():
    """Reading only the generic variable points an HTTP exporter at a gRPC receiver."""
    result = run_probe(
        READERS_PROBE,
        {
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "grpc",
        },
    )
    assert ".proto.grpc." in result["exporters"][0]


def test_metrics_reach_the_endpoint_and_prometheus_still_works(collector):
    port = collector.server_address[1]
    result = run_probe(EXPORT_PROBE, {"OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{port}"})

    assert result["prometheus"] is True

    assert len(collector.requests) == 1
    path, encoding, body = collector.requests[0]
    assert path == "/v1/metrics"
    if encoding == "gzip":
        body = gzip.decompress(body)
    # Parsing the payload is the point: a bare TCP connection must not pass this test.
    request = ExportMetricsServiceRequest()
    request.ParseFromString(body)
    names = [
        metric.name
        for resource_metrics in request.resource_metrics
        for scope_metrics in resource_metrics.scope_metrics
        for metric in scope_metrics.metrics
    ]
    assert "num_files_uploaded" in names


def test_metrics_exporter_none_sends_nothing(collector):
    port = collector.server_address[1]
    result = run_probe(
        EXPORT_PROBE,
        {"OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{port}", "OTEL_METRICS_EXPORTER": "none"},
    )
    assert result["prometheus"] is True
    assert collector.requests == []


def test_llm_metrics_stay_local_and_are_not_pushed_to_the_apm(collector):
    """The metrics half of the boundary ApplicationOnlySpanProcessor enforces for spans."""
    port = collector.server_address[1]
    result = run_probe(LLM_METRIC_PROBE, {"OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{port}"})

    # Local Prometheus is the flow author's own process and keeps seeing everything.
    assert result["prometheus_has_gen_ai"] is True

    assert len(collector.requests) == 1
    _, encoding, body = collector.requests[0]
    if encoding == "gzip":
        body = gzip.decompress(body)
    request = ExportMetricsServiceRequest()
    request.ParseFromString(body)
    scopes = {sm.scope.name for rm in request.resource_metrics for sm in rm.scope_metrics}
    names = [metric.name for rm in request.resource_metrics for sm in rm.scope_metrics for metric in sm.metrics]

    assert "opentelemetry.instrumentation.anthropic" not in scopes
    assert not any("gen_ai" in name for name in names)
    # The application metric in the same export proves the filter dropped a scope, not the batch.
    assert "num_files_uploaded" in names

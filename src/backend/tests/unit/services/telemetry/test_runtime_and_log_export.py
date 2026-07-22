"""Runtime metrics and log export, driven against a real loopback OTLP collector.

The providers are process-global and installed once, so every case runs in a subprocess.
"""

import gzip
import http.server
import json
import os
import subprocess
import sys
import threading

import pytest
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest

# What an operator needs before anything is failing: saturation and runtime health.
EXPECTED_PROCESS_METRICS = {
    "process.cpu.utilization",
    "process.memory.usage",
    "process.thread.count",
}

# Host-level families the default config would have added. They describe the machine, not
# the service, and the disk and network ones multiply per device.
UNWANTED_HOST_METRICS = ("system.disk.", "system.network.", "system.swap.")

SENTINEL_INFO = "operator-visible-info-line"
SENTINEL_DEBUG = "flow-payload-that-must-not-be-shipped"

PROBE = f"""
import logging
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from lfx.log.logger import configure
from lfx.log.logger import logger

otel = OpenTelemetry(prometheus_enabled=False)

# DEBUG so the emitter sees both records and has to make the severity decision itself.
configure(log_level="DEBUG")
logger.debug({SENTINEL_DEBUG!r})
logger.info({SENTINEL_INFO!r})
logger.warning("disk is nearly full")

otel.shutdown()   # flushes both the metric reader and the log processor
print("PROBE_RESULT " + '{{}}')
"""


def run_probe(env_overrides: dict[str, str]) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env.update(env_overrides)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", PROBE],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "PROBE_RESULT" in completed.stdout, completed.stdout


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


def _metric_names(requests) -> set[str]:
    names = set()
    for path, body in requests:
        if path != "/v1/metrics":
            continue
        request = ExportMetricsServiceRequest()
        request.ParseFromString(body)
        for rm in request.resource_metrics:
            for sm in rm.scope_metrics:
                names.update(m.name for m in sm.metrics)
    return names


def _log_records(requests) -> list:
    records = []
    for path, body in requests:
        if path != "/v1/logs":
            continue
        request = ExportLogsServiceRequest()
        request.ParseFromString(body)
        for rl in request.resource_logs:
            for sl in rl.scope_logs:
                records.extend(sl.log_records)
    return records


@pytest.fixture
def exported(collector):
    port = collector.server_address[1]
    run_probe({"OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{port}"})
    return collector.requests


def test_runtime_metrics_reach_the_apm(exported):
    """Without these, the only metrics are request-shaped and saturation is invisible."""
    names = _metric_names(exported)

    assert names >= EXPECTED_PROCESS_METRICS, f"missing: {EXPECTED_PROCESS_METRICS - names}"
    # GC is the Python-specific failure mode: slow service, flat CPU.
    assert any(n.startswith("cpython.gc.") for n in names), sorted(names)


def test_host_level_metrics_are_not_exported(exported):
    """The node belongs to the infrastructure agent; these would only multiply series."""
    names = _metric_names(exported)

    offenders = [n for n in names if n.startswith(UNWANTED_HOST_METRICS)]
    assert not offenders, f"host-level metrics leaked into the export: {offenders}"


def test_log_lines_reach_the_apm(exported):
    """The pivot from a failing trace to the log lines emitted inside it."""
    bodies = [r.body.string_value for r in _log_records(exported)]

    assert SENTINEL_INFO in bodies, bodies
    assert "disk is nearly full" in bodies


def test_debug_lines_are_not_shipped_to_the_operator(exported):
    """The console is the developer's, the APM is the operator's.

    Langflow logs flow outputs at DEBUG, and the redaction processor only scrubs known
    sensitive keys, not free text in a message. So DEBUG stays local unless asked for.
    """
    records = _log_records(exported)
    bodies = [r.body.string_value for r in records]

    assert SENTINEL_DEBUG not in bodies
    assert SENTINEL_DEBUG not in json.dumps([str(r) for r in records])
    assert all(r.severity_number >= 9 for r in records)  # INFO and above


def test_log_severity_is_preserved(exported):
    """An operator alerting on error rate needs the level, not just the text."""
    by_body = {r.body.string_value: r for r in _log_records(exported)}

    assert by_body[SENTINEL_INFO].severity_text == "INFO"
    assert by_body["disk is nearly full"].severity_text == "WARNING"
    assert by_body["disk is nearly full"].severity_number > by_body[SENTINEL_INFO].severity_number


# The incident walk in one probe: a request comes in, something is logged while handling it,
# and the operator pivots from the failing trace to that line by trace id.
INCIDENT_PROBE = """
import json
from opentelemetry import trace, _logs
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.sdk._logs._internal.export.in_memory_log_exporter import InMemoryLogExporter

spans = InMemorySpanExporter()
tp = TracerProvider(); tp.add_span_processor(SimpleSpanProcessor(spans))
trace.set_tracer_provider(tp)

logs = InMemoryLogExporter()
lp = LoggerProvider(); lp.add_log_record_processor(SimpleLogRecordProcessor(logs))
_logs.set_logger_provider(lp)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from lfx.log.logger import configure, logger

configure(log_level="INFO")
app = FastAPI()

@app.get("/boom")
def boom():
    logger.error("payment provider timed out")
    raise RuntimeError("kaboom")

FastAPIInstrumentor.instrument_app(app)

client = TestClient(app, raise_server_exceptions=False)
client.get("/boom")
tp.force_flush(); lp.force_flush()

server_span = [s for s in spans.get_finished_spans() if s.kind.name == "SERVER"][0]
def as_hex(value):
    return format(value, "032x") if value else None

records = [
    {"body": str(r.log_record.body), "trace_id": as_hex(r.log_record.trace_id)}
    for r in logs.get_finished_logs()
]
print("PROBE_RESULT " + json.dumps({
    "span_trace_id": format(server_span.context.trace_id, "032x"),
    "records": records,
}))
"""


def test_a_log_emitted_during_a_request_carries_that_request_trace_id():
    """This is the pivot the incident walk depends on; without it logs and traces are two silos."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", INCIDENT_PROBE],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    result = json.loads(line.removeprefix("PROBE_RESULT "))

    match = [r for r in result["records"] if r["body"] == "payment provider timed out"]
    assert match, result["records"]
    assert match[0]["trace_id"] == result["span_trace_id"]

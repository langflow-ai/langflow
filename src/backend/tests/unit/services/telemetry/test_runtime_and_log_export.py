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
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

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

# Configure logging first, the order both runtimes use: the startup line the bootstrap emits
# only reaches the exporter through the structlog chain this installs.
# DEBUG so the emitter sees both records and has to make the severity decision itself.
configure(log_level="DEBUG")

otel = OpenTelemetry(prometheus_enabled=False)
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


def _log_records(requests, *, scope: str | None = None) -> list:
    """Log records the collector received, optionally only those on one instrumentation scope.

    Scope is the axis the body boundary is drawn on, so several cases below need to ask about
    one side of it at a time.
    """
    records = []
    for path, body in requests:
        if path != "/v1/logs":
            continue
        request = ExportLogsServiceRequest()
        request.ParseFromString(body)
        for rl in request.resource_logs:
            for sl in rl.scope_logs:
                if scope is not None and sl.scope.name != scope:
                    continue
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
    """The pivot from a failing trace to the log lines emitted inside it.

    The record still travels; only its body is withheld. Whether an operator can see the text is
    a separate question from whether the record exists, and alerting on error rate or pivoting
    by trace id needs only the second.
    """
    records = _log_records(exported, scope="lfx")

    assert len(records) >= 2, records
    assert {r.severity_text for r in records} >= {"INFO", "WARNING"}


def test_message_bodies_do_not_cross_the_boundary(exported):
    """The logs signal allowlists by scope, the same rule the span exporter already applies.

    Both sentinels are ordinary application log lines on the default scope, which is the channel
    that carried prompts, chat history and provider error text to the operator's APM.
    """
    payload = json.dumps([str(r) for r in _log_records(exported)])

    assert SENTINEL_INFO not in payload
    assert SENTINEL_DEBUG not in payload


def test_the_startup_line_states_the_boundary(exported):
    """The allowlisted scope keeps its body, and it is what tells the operator what they get.

    Documentation does not reach the person writing the Helm values; a line in their own log
    stream does. It is also the proof that the allowlist lets something through rather than
    being an off switch with extra steps.
    """
    bodies = [r.body.string_value for r in _log_records(exported, scope="langflow.observability")]

    assert any("OTLP log export enabled" in b for b in bodies), bodies
    assert any("bodies are withheld" in b.lower() for b in bodies), bodies
    assert any("container stdout" in b for b in bodies), bodies


def test_debug_lines_are_not_shipped_to_the_operator(exported):
    """The console is the developer's, the APM is the operator's.

    Severity is the first of two gates and still the one that keeps the bulk of flow payload
    logging local; the body boundary above is the second. This asserts the severity gate on its
    own, so a regression in either is attributable.
    """
    records = _log_records(exported)

    assert records, "the probe must export something for this to mean anything"
    assert all(r.severity_number >= 9 for r in records)  # INFO and above


def test_log_severity_is_preserved(exported):
    """An operator alerting on error rate needs the level, and it survives the body boundary."""
    by_severity = {r.severity_text: r for r in _log_records(exported, scope="lfx")}

    assert "INFO" in by_severity, sorted(by_severity)
    assert "WARNING" in by_severity, sorted(by_severity)
    assert by_severity["WARNING"].severity_number > by_severity["INFO"].severity_number


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
    {
        "body": str(r.log_record.body),
        "severity": r.log_record.severity_text,
        "trace_id": as_hex(r.log_record.trace_id),
    }
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

    # Matched on severity rather than text: the body is withheld at the boundary, and the
    # correlation this test exists for is carried by trace_id, which is not.
    match = [r for r in result["records"] if r["severity"] == "ERROR"]
    assert match, result["records"]
    # any(), not match[0]: nothing orders the exported records, and another ERROR arriving
    # first would fail this while correlation itself works.
    assert any(r["trace_id"] == result["span_trace_id"] for r in match), result["records"]
    assert "payment provider timed out" not in json.dumps(result["records"])


# The DEBUG floor is an override, not a lock: an operator debugging a live incident may
# genuinely need it. What must not happen is it moving quietly.
OVERRIDE_PROBE = f"""
from opentelemetry import _logs
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.sdk._logs._internal.export.in_memory_log_exporter import InMemoryLogExporter

exporter = InMemoryLogExporter()
provider = LoggerProvider()
provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
_logs.set_logger_provider(provider)

from lfx.log.logger import configure, logger

configure(log_level="DEBUG")
logger.debug({SENTINEL_DEBUG!r})
logger.info({SENTINEL_INFO!r})
provider.force_flush()

severities = [r.log_record.severity_text for r in exporter.get_finished_logs()]
print("DEBUG_SHIPPED " + str("DEBUG" in severities))
"""


def run_override_probe(value: str | None) -> tuple[bool, str]:
    """Return (was DEBUG exported, whatever went to stderr)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env.pop("LANGFLOW_OTEL_LOG_LEVEL", None)
    if value is not None:
        env["LANGFLOW_OTEL_LOG_LEVEL"] = value
    env["PYTHONWARNINGS"] = "always"
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", OVERRIDE_PROBE],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    shipped = next(ln for ln in completed.stdout.splitlines() if ln.startswith("DEBUG_SHIPPED "))
    return shipped.endswith("True"), completed.stderr


def test_debug_export_is_off_and_silent_by_default():
    shipped, stderr = run_override_probe(None)

    assert shipped is False
    assert "LANGFLOW_OTEL_LOG_LEVEL" not in stderr


def test_lowering_the_floor_works_but_says_so_loudly():
    """Refusing outright would just get worked around; the requirement is that it is not quiet."""
    shipped, stderr = run_override_probe("debug")

    assert shipped is True
    assert "LANGFLOW_OTEL_LOG_LEVEL" in stderr
    # The warning has to name the actual consequence, not just report a setting.
    assert "prompt" in stderr.lower()
    assert "DEBUG" in stderr


def test_an_unrecognised_value_fails_closed_and_warns():
    """A typo must not be a way to accidentally open the floor."""
    shipped, stderr = run_override_probe("verbose")

    assert shipped is False
    assert "LANGFLOW_OTEL_LOG_LEVEL" in stderr
    assert "verbose" in stderr


# The same incident walk, but for a flow run rather than an HTTP request, and driven end to end:
# langflow's real telemetry bootstrap, the real OTLP exporters, and the trace ids read back off
# the protobuf that reached the collector. `lfx serve` is asserted separately, in
# src/lfx/tests/unit/cli/test_serve_app_log_trace_correlation.py, because the two runtimes reach
# the flow span by different paths and only one of them can be true at a time.
FLOW_SENTINEL = "component-log-line-emitted-inside-the-flow-run"

FLOW_PROBE = f"""
import asyncio

from langflow.processing.process import run_graph
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import MessageInput, Output
from lfx.log.logger import configure, logger
from lfx.schema.message import Message


class LoggingComponent(Component):
    display_name = "Logging"
    inputs = [MessageInput(name="input_value", display_name="Input")]
    outputs = [Output(name="message", display_name="Message", method="passthrough")]

    def passthrough(self) -> Message:
        logger.info({FLOW_SENTINEL!r})
        return self.input_value


# Installs the OTLP providers from the OTEL_* env vars, exactly as a langflow server does.
otel = OpenTelemetry(prometheus_enabled=False)
configure(log_level="INFO")

chat_input = ChatInput()
logging_component = LoggingComponent().set(input_value=chat_input.message_response)
chat_output = ChatOutput().set(input_value=logging_component.passthrough)
graph = Graph(chat_input, chat_output, flow_id="00000000-0000-0000-0000-0000000000aa")

asyncio.run(run_graph(graph=graph, input_value="hello", input_type="chat", output_type="chat"))
otel.shutdown()
print("PROBE_RESULT ok")
"""


def _spans(requests) -> list:
    spans = []
    for path, body in requests:
        if path != "/v1/traces":
            continue
        request = ExportTraceServiceRequest()
        request.ParseFromString(body)
        for rs in request.resource_spans:
            for ss in rs.scope_spans:
                spans.extend(ss.spans)
    return spans


@pytest.fixture
def exported_flow_run(collector, tmp_path):
    """Run one real flow under the real bootstrap; return what reached the collector."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{collector.server_address[1]}"
    # The sentinel is how this test finds its own record, and the log body boundary withholds
    # message bodies from the export by default, so without this the match comes back empty and
    # the test fails before it reaches the correlation it exists to check. This test is about
    # correlation, not about that boundary, so ask for bodies explicitly. No-op on a build that
    # predates the setting. The lfx fixture in test_serve_app_log_trace_correlation.py does the
    # same thing for the same reason.
    env["LANGFLOW_OTEL_LOG_BODIES"] = "all"
    # A file rather than ``python -c``: Component.__init__ reads its own class source with
    # inspect.getsource, which has nothing to read for a class defined in a ``-c`` string.
    probe = tmp_path / "flow_probe.py"
    probe.write_text(FLOW_PROBE)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(probe)],
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "PROBE_RESULT ok" in completed.stdout, completed.stdout
    return collector.requests


def test_a_log_line_from_a_flow_run_carries_the_flow_span_trace_id(exported_flow_run):
    """The pivot from a flow's trace to its logs. Without it the two signals are separate silos."""
    flow_span = next(s for s in _spans(exported_flow_run) if s.name == "flow.execute")
    matching = [r for r in _log_records(exported_flow_run) if r.body.string_value == FLOW_SENTINEL]

    assert matching, [r.body.string_value for r in _log_records(exported_flow_run)]
    # A zeroed trace id is what "no active span" looks like on the wire, so it would pass a
    # naive equality check against another zeroed one.
    assert flow_span.trace_id != b"\x00" * 16
    assert matching[0].trace_id == flow_span.trace_id, (
        f"log trace_id {matching[0].trace_id.hex()} != span trace_id {flow_span.trace_id.hex()}"
    )

"""Log-to-trace correlation for ``lfx serve``, driven against a real loopback OTLP collector.

The incident walk this exists for: an operator sees a slow or failing flow run in their APM,
clicks the trace, and expects the log lines emitted *inside* that run to be sitting there. That
only works if the log records carry the same trace id as the exported span, and nothing in the
code makes that true explicitly -- it falls out of the OTel context, which means it can break
silently. Asserting that the log processor is installed would not catch that; this drives the
real bootstrap, real OTLP exporters, and a real HTTP round trip, then reads the trace id off the
protobuf that actually reached the collector.

The providers are process-global and installed once per process, so the run happens in a
subprocess (same reason as tests/unit/services/telemetry in the langflow tree).
"""

import gzip
import http.server
import os
import subprocess
import sys
import threading

import pytest
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

FLOW_ID = "00000000-0000-0000-0000-0000000000aa"
API_KEY = "correlation-probe-key"  # pragma: allowlist secret
# Logged from inside a component, so it is emitted while the flow span is the unit of work --
# not from the request handler around it.
SENTINEL = "component-log-line-emitted-inside-the-flow-run"

PROBE = f"""
import os

from fastapi.testclient import TestClient
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app
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
        logger.info({SENTINEL!r})
        return self.input_value


chat_input = ChatInput()
logging_component = LoggingComponent().set(input_value=chat_input.message_response)
chat_output = ChatOutput().set(input_value=logging_component.passthrough)
graph = Graph(chat_input, chat_output, flow_id={FLOW_ID!r})

configure(log_level="INFO")
os.environ["LANGFLOW_API_KEY"] = {API_KEY!r}

registry = FlowRegistry()
registry.add(graph, FlowMeta(id={FLOW_ID!r}, relative_path="probe.py", title="Probe", description=None))
# Installs the OTLP providers from the OTEL_* env vars, exactly as a real `lfx serve` worker does.
app = create_multi_serve_app(registry=registry)

# The context manager runs the lifespan, whose shutdown flushes the OTLP buffers.
with TestClient(app) as client:
    response = client.post(
        "/flows/{FLOW_ID}/run",
        json={{"input_value": "hello"}},
        headers={{"x-api-key": {API_KEY!r}}},
    )
    assert response.status_code == 200, response.text

print("PROBE_RESULT ok")
"""


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


@pytest.fixture
def exported(collector, tmp_path):
    """Run one flow through a real serve app exporting to the collector; return its requests."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{collector.server_address[1]}"
    # The sentinel is how this test finds its own log record, and the body boundary withholds
    # message bodies from the export by default. This test is about correlation, not about that
    # boundary, so ask for bodies explicitly rather than have the discriminator disappear. No-op
    # on a build that predates the setting.
    env["LANGFLOW_OTEL_LOG_BODIES"] = "all"
    # A file rather than ``python -c``: Component.__init__ reads its own class source with
    # inspect.getsource, which has nothing to read for a class defined in a ``-c`` string.
    probe = tmp_path / "probe.py"
    probe.write_text(PROBE)
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


def test_the_flow_run_exports_a_span(exported):
    """Precondition for the correlation assertion below: there is a flow span to correlate to."""
    names = [s.name for s in _spans(exported)]

    assert "flow.execute" in names, names


def test_a_log_line_from_the_flow_run_carries_the_flow_span_trace_id(exported):
    """The pivot from a flow's trace to its logs. Without it the two signals are separate silos."""
    flow_span = next(s for s in _spans(exported) if s.name == "flow.execute")
    matching = [r for r in _log_records(exported) if r.body.string_value == SENTINEL]

    assert matching, [r.body.string_value for r in _log_records(exported)]
    # A zeroed trace id is what "no active span" looks like on the wire, so it would pass a
    # naive equality check against another zeroed one.
    assert flow_span.trace_id != b"\x00" * 16
    assert matching[0].trace_id == flow_span.trace_id, (
        f"log trace_id {matching[0].trace_id.hex()} != span trace_id {flow_span.trace_id.hex()}"
    )


def test_the_request_span_shares_that_trace_id_too(exported):
    """The pivot an operator actually starts from is the failing request, not the flow span.

    Correlating the log to ``flow.execute`` alone would still hold if the flow span had started
    its own trace, and then the request an operator is looking at in their APM would not lead
    to either. Asserting all three share one id is what makes the walk end where it started.
    """
    spans = _spans(exported)
    flow_span = next(s for s in spans if s.name == "flow.execute")
    # SPAN_KIND_SERVER is 2; the FastAPI instrumentation names it after the route.
    server_spans = [s for s in spans if s.kind == 2]
    matching = [r for r in _log_records(exported) if r.body.string_value == SENTINEL]

    assert server_spans, [s.name for s in spans]
    assert matching
    assert server_spans[0].trace_id != b"\x00" * 16
    assert server_spans[0].trace_id == flow_span.trace_id, (
        f"request {server_spans[0].trace_id.hex()} != flow {flow_span.trace_id.hex()}"
    )
    assert server_spans[0].trace_id == matching[0].trace_id

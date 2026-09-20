"""``lfx run`` must deliver its flow span over the production OTLP pipeline, not only label it.

The sibling ``test_run_command_flow_span.py`` installs an in-memory tracer provider before it
invokes the command, which proves the ``protocol`` attribute is bound on the right span. It
cannot prove what an operator actually gets, which needs two things the command itself has to
do: install the providers from ``OTEL_EXPORTER_OTLP_*`` and flush them before the one-shot
process exits. Neither happened: the command never called
:func:`lfx.observability.bootstrap_application_telemetry`, so the span landed on OpenTelemetry's
no-op proxy provider and every ``lfx run`` wired into an APM was a silently blind surface.

This drives the real console entry point in a subprocess, with the standard environment
variables pointed at a loopback OTLP/HTTP collector, and reads the span off the protobuf that
arrived. The batch processor's own export timer is pushed out to ten minutes, so the only thing
that can deliver the span is the explicit flush on exit; a run that exported only because the
timer happened to fire would not pass here.
"""

import gzip
import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

# opentelemetry is an optional lfx extra (``lfx[otel]``); skip rather than error on an install
# that did not opt in, matching the sibling probes. Probed through the OTLP/HTTP trace exporter
# rather than the bare ``opentelemetry`` namespace, which opentelemetry-api alone satisfies: this
# file needs the exporter the command installs in the subprocess and the proto module the
# collector decodes with, and the exporter import brings both (plus the SDK) or fails.
pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")
from lfx.observability import APPLICATION_TRACER_NAME
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

FLOW = Path(__file__).resolve().parents[2] / "data" / "simple_chat_no_llm.json"

# A flow whose component raises, so the run ends with the error JSON and exit code 1. The span
# for that run is the one an operator most needs delivered: it is the only record that a cron
# job or CI step failed, and it must not be lost to a flush that only happens on success.
FAILING_FLOW_SCRIPT = """
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import MessageInput, Output
from lfx.schema.message import Message


class ExplodingComponent(Component):
    display_name = "Exploding"
    inputs = [MessageInput(name="input_value", display_name="Input")]
    outputs = [Output(name="message", display_name="Message", method="explode")]

    def explode(self) -> Message:
        msg = "inventory service returned 503"
        raise RuntimeError(msg)


chat_input = ChatInput()
exploding = ExplodingComponent().set(input_value=chat_input.message_response)
chat_output = ChatOutput().set(input_value=exploding.explode)
graph = Graph(chat_input, chat_output)
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


def _run_cli(collector, *args: str) -> subprocess.CompletedProcess:
    """Run ``lfx run`` exactly as an operator would, exporting to the loopback collector."""
    # Start from a clean slate so the developer's own OTEL_* vars cannot skew the result.
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{collector.server_address[1]}"
    # Ten minutes: the span must arrive because the command flushed on exit, not because the
    # batch processor's timer fired while the run was still going.
    env["OTEL_BSP_SCHEDULE_DELAY"] = "600000"
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "lfx", "run", *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _flow_spans(requests) -> list[dict]:
    spans = []
    for path, body in requests:
        if path != "/v1/traces":
            continue
        request = ExportTraceServiceRequest()
        request.ParseFromString(body)
        for resource_spans in request.resource_spans:
            for scope_spans in resource_spans.scope_spans:
                for span in scope_spans.spans:
                    if span.name != "flow.execute":
                        continue
                    spans.append(
                        {
                            "scope": scope_spans.scope.name,
                            "attrs": {a.key: a.value.string_value for a in span.attributes},
                        }
                    )
    return spans


def _the_one_json_line(stdout: str) -> dict:
    """The CLI's stdout contract: one JSON document, nothing else. Telemetry must not break it."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert len(lines) == 1, stdout
    return json.loads(lines[0])


def test_a_run_exports_its_flow_span_over_otlp(collector):
    completed = _run_cli(collector, str(FLOW), "--input-value", "hello operator")

    assert completed.returncode == 0, completed.stderr
    assert _the_one_json_line(completed.stdout)["success"] is True

    spans = _flow_spans(collector.requests)
    assert len(spans) == 1, f"expected exactly one flow span at the collector, got {spans}"
    assert spans[0]["scope"] == APPLICATION_TRACER_NAME
    assert spans[0]["attrs"]["protocol"] == "lfx.run"
    assert spans[0]["attrs"]["status"] == "ok"


def test_a_failed_run_still_exports_its_flow_span(collector, tmp_path):
    # A file rather than inline JSON: Component.__init__ reads its own class source with
    # inspect.getsource, which has nothing to read for a class defined in a ``-c`` string.
    script = tmp_path / "failing_flow.py"
    script.write_text(FAILING_FLOW_SCRIPT, encoding="utf-8")

    completed = _run_cli(collector, str(script), "--input-value", "hello operator")

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert _the_one_json_line(completed.stdout)["success"] is False

    spans = _flow_spans(collector.requests)
    assert len(spans) == 1, f"expected exactly one flow span at the collector, got {spans}"
    assert spans[0]["attrs"]["protocol"] == "lfx.run"
    assert spans[0]["attrs"]["status"] == "error"
    assert spans[0]["attrs"].get("error.type"), spans[0]["attrs"]

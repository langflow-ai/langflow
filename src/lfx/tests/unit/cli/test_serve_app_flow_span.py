"""``lfx serve``'s native run route must label its flow span like every other surface.

The app mounts two things that execute flows: the v2 workflow router and serve_app's own
``/flows/{id}/run`` and ``/flows/{id}/stream``. Both reach the graph, so both must carry the
same ``protocol``, or an operator reading the APM sees half of ``lfx serve``'s traffic as an
unwired path (an absent protocol attribute is deliberately the signal for that).

Runs in a subprocess because the tracer provider is process-global and installed once.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# opentelemetry is an optional lfx extra (``lfx[otel]``), and the probe below imports it in a
# subprocess that inherits this interpreter. Without the guard this errors instead of skipping
# on an lfx install that did not opt in, which is exactly what the isolated lfx CI job is.
pytest.importorskip("opentelemetry")

FLOW_ID = "22222222-2222-2222-2222-222222222222"
API_KEY = "probe-key"  # pragma: allowlist secret

PROBE = f"""
import asyncio, json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

from httpx import ASGITransport, AsyncClient

from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph

FLOW_ID = {FLOW_ID!r}


def build_graph():
    chat_input = ChatInput(_id="chat-input")
    chat_output = ChatOutput(_id="chat-output")
    chat_output.set(input_value=chat_input.message_response)
    return Graph(chat_input, chat_output, flow_id=FLOW_ID)


async def main():
    registry = FlowRegistry()
    registry.add(build_graph(), FlowMeta(id=FLOW_ID, relative_path="probe.json", title="probe"))
    app = create_multi_serve_app(registry=registry)
    # The real auth dependency, given the key it expects, rather than an override.
    app.state.expected_api_key = {API_KEY!r}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://probe") as client:
        response = await client.post(
            f"/flows/{{FLOW_ID}}/run",
            json={{"input_value": "hello operator"}},
            headers={{"x-api-key": {API_KEY!r}}},
        )

    provider.force_flush()
    spans = [
        {{"name": s.name, "attrs": dict(s.attributes)}}
        for s in exporter.get_finished_spans()
        if s.name == "flow.execute"
    ]
    print("PROBE_RESULT " + json.dumps({{"status_code": response.status_code, "spans": spans}}))


asyncio.run(main())
"""


def run_probe(source: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    with tempfile.TemporaryDirectory() as tmp:
        # A file rather than -c: Component.__init__ reads its own class source with inspect.
        probe_path = Path(tmp) / "probe.py"
        probe_path.write_text(source, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    return json.loads(line.removeprefix("PROBE_RESULT "))


def test_the_native_serve_run_route_labels_its_flow_span():
    result = run_probe(PROBE)
    assert result["status_code"] == 200, result

    assert len(result["spans"]) == 1, f"expected one flow span, got {result['spans']}"
    attrs = result["spans"][0]["attrs"]
    assert attrs["protocol"] == "lfx.serve"
    assert attrs["flow_id"] == FLOW_ID
    assert attrs["status"] == "ok"

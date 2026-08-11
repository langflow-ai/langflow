"""The tracer provider is process-global and installed once, so each case runs in a subprocess."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from langflow.services.telemetry.opentelemetry import APPLICATION_INSTRUMENTATION_SCOPES
from lfx.observability import APPLICATION_TRACER_NAME

PROVIDER_SETUP = """
import asyncio, json
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph

def build_graph():
    chat_input = ChatInput(_id="chat-input")
    chat_input.set(input_value="hello operator")
    chat_output = ChatOutput(_id="chat-output")
    chat_output.set(input_value=chat_input.message_response)
    return Graph(chat_input, chat_output, flow_id="11111111-1111-1111-1111-111111111111")

def report(result):
    provider.force_flush()
    result["spans"] = [
        {
            "name": span.name,
            "scope": span.instrumentation_scope.name,
            "attrs": dict(span.attributes),
            "status": span.status.status_code.name,
            "description": span.status.description,
            "span_id": span.context.span_id,
            "parent_span_id": span.parent.span_id if span.parent else None,
        }
        for span in exporter.get_finished_spans()
    ]
    print("PROBE_RESULT " + json.dumps(result))
"""

ASYNC_START_PROBE = (
    PROVIDER_SETUP
    + """
async def main():
    graph = build_graph()
    ran = []
    async for step in graph.async_start():
        if hasattr(step, "vertex"):
            ran.append(step.vertex.id)
    report({"ran": ran})

asyncio.run(main())
"""
)

ARUN_PROBE = (
    PROVIDER_SETUP
    + """
async def main():
    graph = build_graph()
    run_outputs = await graph.arun(inputs=[{}], outputs=["chat-output"], session_id="session-abc")
    text = run_outputs[0].outputs[0].results["message"].text
    report({"text": text})

asyncio.run(main())
"""
)

SENTINEL = "prompt-text-that-must-not-be-exported"

FAILING_PROBE = (
    PROVIDER_SETUP
    + f"""
from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

class Boom(Component):
    display_name = "Boom"
    inputs = [MessageTextInput(name="input_value", display_name="Input")]
    outputs = [Output(name="message", display_name="Message", method="explode")]

    def explode(self) -> Message:
        raise RuntimeError({SENTINEL!r})

async def main():
    chat_input = ChatInput(_id="chat-input")
    chat_input.set(input_value="hello operator")
    boom = Boom(_id="boom")
    boom.set(input_value=chat_input.message_response)
    graph = Graph(chat_input, boom, flow_id="11111111-1111-1111-1111-111111111111")
    error = None
    try:
        await graph.arun(inputs=[{{}}], outputs=["boom"])
    except Exception as exc:  # noqa: BLE001
        error = type(exc).__name__
    report({{"error": error}})

asyncio.run(main())
"""
)

# A Loop runs its body as a subgraph, so without the guard a loop over N items would bury the
# operator's flow.execute span under N identical ones.
SUBGRAPH_PROBE = (
    PROVIDER_SETUP
    + """
async def main():
    graph = build_graph()
    graph.prepare()
    async with graph.create_subgraph({"chat-input", "chat-output"}) as subgraph:
        assert subgraph._is_subgraph is True
        spans_before = len(exporter.get_finished_spans())
        with subgraph.flow_execution_span():
            pass
        opened = len(exporter.get_finished_spans()) - spans_before
    report({"opened": opened})

asyncio.run(main())
"""
)

# A HITL pause is a suspend, not a failure. The resume is a separate span, opened by whichever
# runner drives Graph.process next.
PAUSED_PROBE = (
    PROVIDER_SETUP
    + """
from lfx.graph.exceptions import GraphPausedException

async def main():
    graph = build_graph()
    raised = False
    try:
        with graph.flow_execution_span():
            raise GraphPausedException(checkpoint_id="checkpoint-1", reason="waiting on a human")
    except GraphPausedException:
        raised = True
    report({"raised": raised})

asyncio.run(main())
"""
)

# flow-as-tool runs a whole child Graph inside a component of the parent flow.
NESTED_PROBE = (
    PROVIDER_SETUP
    + """
async def main():
    parent = build_graph()
    with parent.flow_execution_span():
        child = build_graph()
        await child.arun(inputs=[{}], outputs=["chat-output"], session_id="child-session")
    report({})

asyncio.run(main())
"""
)

NO_OTEL_PROBE = """
import asyncio, json, sys

sys.modules["opentelemetry"] = None
sys.modules["opentelemetry.trace"] = None

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph
import lfx.graph.graph.base as graph_base

assert graph_base.otel_trace is None, "guard did not trip"

async def main():
    chat_input = ChatInput(_id="chat-input")
    chat_input.set(input_value="hello operator")
    chat_output = ChatOutput(_id="chat-output")
    chat_output.set(input_value=chat_input.message_response)
    graph = Graph(chat_input, chat_output, flow_id="11111111-1111-1111-1111-111111111111")
    ran = []
    async for step in graph.async_start():
        if hasattr(step, "vertex"):
            ran.append(step.vertex.id)
    print("PROBE_RESULT " + json.dumps({"ran": ran}))

asyncio.run(main())
"""


def run_probe(source: str) -> dict:
    # Start from a clean slate so the developer's own OTEL_* vars cannot skew the result.
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


def test_lfx_tracer_name_is_allowlisted_by_langflow():
    """Drift between the two constants would silently drop every application span."""
    assert APPLICATION_TRACER_NAME in APPLICATION_INSTRUMENTATION_SCOPES


def test_async_start_emits_one_application_span():
    result = run_probe(ASYNC_START_PROBE)
    assert result["ran"] == ["chat-input", "chat-output"]

    # Exactly one span is also the assertion that no component-level spans are produced.
    assert len(result["spans"]) == 1
    span = result["spans"][0]
    assert span["name"] == "flow.execute"
    assert span["scope"] == APPLICATION_TRACER_NAME
    assert span["attrs"]["flow_id"] == "11111111-1111-1111-1111-111111111111"
    assert span["attrs"]["run_id"]


def test_arun_emits_one_application_span():
    result = run_probe(ARUN_PROBE)
    assert result["text"] == "hello operator"

    assert len(result["spans"]) == 1
    span = result["spans"][0]
    assert span["name"] == "flow.execute"
    assert span["scope"] == APPLICATION_TRACER_NAME
    assert set(span["attrs"]) == {"flow_id", "run_id", "session_id"}
    assert span["attrs"]["session_id"] == "session-abc"
    assert span["status"] == "UNSET"


def test_failing_flow_marks_the_span_as_an_error_without_leaking_the_message():
    result = run_probe(FAILING_PROBE)
    assert result["error"] == "ValueError"

    assert len(result["spans"]) == 1
    span = result["spans"][0]
    assert span["status"] == "ERROR"
    assert span["attrs"]["error.type"] == "ValueError"
    # The wrapped message embeds component output, which must not reach the operator's APM.
    assert SENTINEL not in json.dumps(span)


def test_flow_runs_with_no_opentelemetry_installed():
    result = run_probe(NO_OTEL_PROBE)
    assert result["ran"] == ["chat-input", "chat-output"]


def test_subgraph_does_not_open_its_own_span():
    result = run_probe(SUBGRAPH_PROBE)
    assert result["opened"] == 0
    assert result["spans"] == []


def test_a_paused_flow_is_not_recorded_as_an_error():
    result = run_probe(PAUSED_PROBE)
    assert result["raised"] is True

    assert len(result["spans"]) == 1
    span = result["spans"][0]
    assert span["status"] == "UNSET"
    assert "error.type" not in span["attrs"]


def test_a_flow_run_from_inside_a_flow_nests_under_its_caller():
    result = run_probe(NESTED_PROBE)

    # Child ends first, so it is the one the exporter sees first.
    child, parent = result["spans"]
    assert child["attrs"]["session_id"] == "child-session"
    assert child["parent_span_id"] == parent["span_id"]

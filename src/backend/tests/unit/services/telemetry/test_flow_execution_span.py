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
            "links": [link.context.span_id for link in span.links],
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
        raise KeyError({SENTINEL!r})

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

# A driver that outlives its request still has the request's span in context, because
# asyncio.create_task copies it. Parenting to a span that has already ended renders as a child
# starting after its parent finished, so the run becomes its own root and links back instead.
DEAD_PARENT_PROBE = (
    PROVIDER_SETUP
    + """
from opentelemetry import trace as otel_trace

async def main():
    tracer = otel_trace.get_tracer("probe.request")
    request_span = tracer.start_span("POST /api/v1/build")
    request_id = request_span.get_span_context().span_id
    with otel_trace.use_span(request_span, end_on_exit=False):
        # The route returns here and the work carries on in the copied context.
        request_span.end()
        graph = build_graph()
        await graph.arun(inputs=[{}], outputs=["chat-output"])
    report({"request_span_id": request_id})

asyncio.run(main())
"""
)

# The same context, but the request is still open (the v2 stream holds its server span for the
# whole response). That is a real parent and must be left as one.
LIVE_PARENT_PROBE = (
    PROVIDER_SETUP
    + """
from opentelemetry import trace as otel_trace

async def main():
    tracer = otel_trace.get_tracer("probe.request")
    request_span = tracer.start_span("POST /api/v2/workflows")
    request_id = request_span.get_span_context().span_id
    with otel_trace.use_span(request_span, end_on_exit=True):
        graph = build_graph()
        await graph.arun(inputs=[{}], outputs=["chat-output"])
    report({"request_span_id": request_id})

asyncio.run(main())
"""
)

PROTOCOL_PROBE = (
    PROVIDER_SETUP
    + """
from lfx.observability import execution_protocol

async def main():
    graph = build_graph()
    with execution_protocol("webhook"):
        await graph.arun(inputs=[{}], outputs=["chat-output"])
    report({})

asyncio.run(main())
"""
)

# Several surfaces share one driver (voice reaches the graph through the build loop), so the
# inner generic binding must not overwrite the outer one that knows how the request actually
# arrived. The pair here is the real one: voice enters through build_flow_and_stream, which
# binds v1.build for itself.
NESTED_PROTOCOL_PROBE = (
    PROVIDER_SETUP
    + """
from lfx.observability import execution_protocol, get_execution_protocol

async def main():
    graph = build_graph()
    with execution_protocol("voice"):
        with execution_protocol("v1.build"):
            inner = get_execution_protocol()
            await graph.arun(inputs=[{}], outputs=["chat-output"])
    after = get_execution_protocol()
    report({"inner": inner, "after": after})

asyncio.run(main())
"""
)

# CancelledError is a BaseException, so an `except Exception` handler never sees it. A user
# pressing stop and the v2 execution ceiling both cancel the driver this span wraps.
CANCELLED_PROBE = (
    PROVIDER_SETUP
    + """
async def main():
    graph = build_graph()
    raised = False
    try:
        with graph.flow_execution_span():
            raise asyncio.CancelledError()
    except asyncio.CancelledError:
        raised = True
    report({"raised": raised})

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
    assert set(span["attrs"]) == {"flow_id", "run_id", "session_id", "status"}
    assert span["attrs"]["session_id"] == "session-abc"
    assert span["attrs"]["status"] == "ok"
    # No surface bound one, so the attribute is absent rather than guessed. An operator seeing a
    # protocol-less flow span is looking at a genuinely unwired path.
    assert "protocol" not in span["attrs"]
    assert span["status"] == "UNSET"


def test_failing_flow_marks_the_span_as_an_error_without_leaking_the_message():
    result = run_probe(FAILING_PROBE)
    # Graph execution wraps the component failure for the API, but telemetry must classify the
    # actionable root cause rather than the wrapper shared by unrelated failures.
    assert result["error"] == "ValueError"

    assert len(result["spans"]) == 1
    span = result["spans"][0]
    assert span["status"] == "ERROR"
    assert span["description"] == "KeyError"
    assert span["attrs"]["status"] == "error"
    assert span["attrs"]["error.type"] == "KeyError"
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
    # Span status stays UNSET so a pause never counts toward the error rate, but the attribute
    # tells a paused run apart from a finished one, which UNSET alone cannot.
    assert span["status"] == "UNSET"
    assert span["attrs"]["status"] == "paused"
    assert "error.type" not in span["attrs"]


def test_a_flow_run_from_inside_a_flow_nests_under_its_caller():
    result = run_probe(NESTED_PROBE)

    # Child ends first, so it is the one the exporter sees first.
    child, parent = result["spans"]
    assert child["attrs"]["session_id"] == "child-session"
    assert child["parent_span_id"] == parent["span_id"]


def test_the_span_records_the_surface_the_run_arrived_through():
    result = run_probe(PROTOCOL_PROBE)

    assert len(result["spans"]) == 1
    assert result["spans"][0]["attrs"]["protocol"] == "webhook"


def test_an_inner_binding_does_not_overwrite_the_surface_that_took_the_request():
    result = run_probe(NESTED_PROTOCOL_PROBE)

    assert result["inner"] == "voice", "the inner generic driver overwrote the real surface"
    assert len(result["spans"]) == 1
    assert result["spans"][0]["attrs"]["protocol"] == "voice"
    # Reset on exit, so a worker reusing this task for the next request starts unbound.
    assert result["after"] is None


def test_a_run_that_outlives_its_request_becomes_its_own_root():
    """A run that outlives its request gets its own trace root.

    The v1 build route returns the job_id and keeps working, so its server span is already
    closed. A child of a finished parent is a broken trace in any APM that renders the tree.
    """
    result = run_probe(DEAD_PARENT_PROBE)

    flow_spans = [span for span in result["spans"] if span["name"] == "flow.execute"]
    assert len(flow_spans) == 1
    span = flow_spans[0]
    assert span["parent_span_id"] is None, "the flow span adopted a parent that had already ended"
    # The request stays reachable from the run; it just is not pretended to contain it.
    assert span["links"] == [result["request_span_id"]]


def test_a_run_inside_a_live_request_still_nests_under_it():
    """A run inside a still-open request keeps nesting under it.

    The other half of the same rule: the v2 stream holds its server span open for the whole
    response, so that one is a real parent and detaching it would lose the correlation.
    """
    result = run_probe(LIVE_PARENT_PROBE)

    flow_spans = [span for span in result["spans"] if span["name"] == "flow.execute"]
    assert len(flow_spans) == 1
    span = flow_spans[0]
    assert span["parent_span_id"] == result["request_span_id"]
    assert span["links"] == []


def test_a_cancelled_flow_is_not_recorded_as_a_successful_one():
    result = run_probe(CANCELLED_PROBE)
    assert result["raised"] is True

    assert len(result["spans"]) == 1
    span = result["spans"][0]
    assert span["attrs"]["status"] == "cancelled"
    # A withdrawn request is not a service fault, so it must not land on the error rate.
    assert span["status"] == "UNSET"
    assert "error.type" not in span["attrs"]

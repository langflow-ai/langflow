"""Who opens the flow span for a run driven through ``async_start``.

``async_start`` is an async generator, so a span it opens cannot be made current: the context
token would be attached and detached across the generator's suspension points and leak into
whatever task resumed it. A span that is not current cannot parent anything, so every span the
run produces (MCP tool calls, database queries) sits beside the flow span rather than under it.

The fix is for the caller to open the span, because the callers are coroutines and thread entry
points, which have no such problem. ``open_flow_span=False`` says that has happened.

Runs in a subprocess because the tracer provider is process-global.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry")

PROBE = """
import asyncio, json, sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.io import Output
from lfx.observability import APPLICATION_TRACER_NAME

MODE = sys.argv[1]


def build():
    chat_input = ChatInput(_id="chat-input")
    chat_input.set(input_value="hello")
    chat_output = ChatOutput(_id="chat-output")
    chat_output.set(input_value=chat_input.message_response)
    return Graph(chat_input, chat_output, flow_id="11111111-1111-1111-1111-111111111111")


async def main():
    graph = build()
    tracer = trace.get_tracer(APPLICATION_TRACER_NAME)
    inner_parent = None
    caller_ids = None
    raised = None

    if MODE == "caller_opens":
        with graph.flow_execution_span():
            async for _ in graph.async_start(open_flow_span=False):
                if inner_parent is None:
                    # A span opened mid-run stands in for anything the graph does: an MCP tool
                    # call, a database query. What matters is what it parents to.
                    with tracer.start_as_current_span("probe.inner") as inner:
                        inner_parent = inner.parent.span_id if inner.parent else None
    elif MODE == "async_start_opens":
        async for _ in graph.async_start():
            if inner_parent is None:
                with tracer.start_as_current_span("probe.inner") as inner:
                    inner_parent = inner.parent.span_id if inner.parent else None
    elif MODE == "deferred_but_nobody_opened":
        async for _ in graph.async_start(open_flow_span=False):
            pass
    elif MODE in ("sync_start_value_error", "sync_start_other_error"):
        # A failure has to leave the span scope for the span to see it. Two kinds, because the
        # handler that used to sit inside that scope only named ValueError: async_start raises a
        # raw ValueError when a cyclic graph hits max_iterations, while a component failure
        # arrives wrapped as ComponentBuildError and took the other path entirely.
        if MODE == "sync_start_value_error":
            from lfx.components.input_output import TextInputComponent, TextOutputComponent
            from lfx.components.logic.conditional_router import ConditionalRouterComponent
            from lfx.custom import Component
            from lfx.io import MessageTextInput
            from lfx.schema.message import Message

            class Concatenate(Component):
                display_name = "Concatenate"
                name = "Concatenate"
                inputs = [MessageTextInput(name="text", display_name="Text", required=False)]
                outputs = [Output(display_name="Message", name="some_text", method="concatenate")]

                def concatenate(self) -> Message:
                    return Message(text=f"{self.text}{self.text}" or "test")

            text_input = TextInputComponent(_id="text_input")
            router = ConditionalRouterComponent(_id="router")
            text_input.set(input_value=router.false_response)
            concat = Concatenate(_id="concatenate")
            concat.set(text=text_input.text_response)
            router.set(
                input_text=text_input.text_response,
                match_text="testtesttesttest",
                operator="equals",
                false_case_message=concat.concatenate,
            )
            text_output = TextOutputComponent(_id="text_output")
            text_output.set(input_value=router.true_response)
            end = ChatOutput(_id="chat_output")
            end.set(input_value=text_output.text_response)
            failing_graph = Graph(text_input, end)
            runner = lambda: list(failing_graph.start(max_iterations=2, config={"output": {"cache": False}}))
        else:
            from lfx.custom import Component
            from lfx.io import MessageInput
            from lfx.schema.message import Message

            class Exploding(Component):
                display_name = "Exploding"
                name = "Exploding"
                inputs = [MessageInput(name="input_value", display_name="Input")]
                outputs = [Output(name="message", display_name="Message", method="respond")]

                def respond(self) -> Message:
                    raise TypeError("not a ValueError")

            chat_input = ChatInput(_id="chat-input")
            chat_input.set(input_value="hello")
            middle = Exploding(_id="exploding")
            middle.set(input_value=chat_input.message_response)
            chat_output = ChatOutput(_id="chat-output")
            chat_output.set(input_value=middle.respond)
            failing_graph = Graph(chat_input, chat_output, flow_id="11111111-1111-1111-1111-111111111111")
            runner = lambda: list(failing_graph.start())

        try:
            runner()
        except Exception as exc:  # noqa: BLE001 - the probe reports it rather than failing
            raised = type(exc).__name__
    elif MODE == "sync_start_under_a_caller_span":
        # The sync entry point hands the run to a worker thread, and a new thread starts with an
        # empty context, so the flow span has to be given the caller's or it begins its own trace.
        with tracer.start_as_current_span("caller") as caller:
            caller_context = caller.get_span_context()
            list(graph.start())
        caller_ids = (caller_context.trace_id, caller_context.span_id)

    provider.force_flush()
    spans = [
        {
            "name": s.name,
            "span_id": s.context.span_id,
            "trace_id": s.context.trace_id,
            "parent": s.parent.span_id if s.parent else None,
            "links": [link.context.span_id for link in s.links],
            "status": (s.attributes or {}).get("status"),
            "error_type": (s.attributes or {}).get("error.type"),
        }
        for s in exporter.get_finished_spans()
    ]
    print(
        "PROBE_RESULT "
        + json.dumps(
            {
                "spans": spans,
                "inner_parent": inner_parent,
                "caller_trace": caller_ids[0] if caller_ids else None,
                "caller_span": caller_ids[1] if caller_ids else None,
                "raised": raised,
            }
        )
    )


asyncio.run(main())
"""


def run_probe(mode: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    with tempfile.TemporaryDirectory() as tmp:
        probe_path = Path(tmp) / "probe.py"
        probe_path.write_text(PROBE, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe_path), mode],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    return json.loads(line.removeprefix("PROBE_RESULT "))


def test_a_caller_opened_span_parents_what_the_run_does():
    """The converted shape. This is the whole point of moving the span to the caller."""
    result = run_probe("caller_opens")

    flow_spans = [s for s in result["spans"] if s["name"] == "flow.execute"]
    assert len(flow_spans) == 1, "the caller's span should be the only flow span"
    assert result["inner_parent"] == flow_spans[0]["span_id"]


def test_async_start_still_opens_its_own_span_when_the_caller_does_not():
    """An unconverted caller keeps today's behaviour rather than silently losing telemetry.

    The span exists, and it still cannot parent the run, which is the limitation the flag exists
    to let callers opt out of.
    """
    result = run_probe("async_start_opens")

    flow_spans = [s for s in result["spans"] if s["name"] == "flow.execute"]
    assert len(flow_spans) == 1
    assert result["inner_parent"] != flow_spans[0]["span_id"]


def test_deferring_without_opening_one_emits_no_flow_span():
    """The mistake the flag makes possible. It is silent, which is why async_start warns."""
    result = run_probe("deferred_but_nobody_opened")

    assert [s for s in result["spans"] if s["name"] == "flow.execute"] == []


def test_the_sync_start_runs_under_the_caller_span():
    """``Graph.start`` hands the run to a worker thread, and a thread starts with no context.

    Without the caller's context copied in, the flow span finds no current span and opens a
    brand-new trace. Measured before the fix: different trace ids, no parent and no link, so a
    caller's span and the run it started were two unrelated traces in the operator's APM.

    The trace id is the assertion that matters. A parent alone could be satisfied by a span that
    happened to nest under something else in the worker.
    """
    result = run_probe("sync_start_under_a_caller_span")

    flow_spans = [s for s in result["spans"] if s["name"] == "flow.execute"]
    assert len(flow_spans) == 1, result["spans"]
    assert result["caller_trace"], "the probe did not record a caller span"

    assert flow_spans[0]["trace_id"] == result["caller_trace"], (
        f"flow span is in trace {flow_spans[0]['trace_id']:032x}, caller is in {result['caller_trace']:032x}"
    )
    assert flow_spans[0]["parent"] == result["caller_span"]


@pytest.mark.parametrize(
    ("mode", "expected_raised", "expected_error_type"),
    [
        ("sync_start_value_error", "ValueError", "ValueError"),
        ("sync_start_other_error", "ComponentBuildError", "TypeError"),
    ],
)
def test_a_failing_sync_run_reaches_the_caller_and_the_span(mode: str, expected_raised: str, expected_error_type: str):
    """A failure has to leave the span scope, then be caught at the worker boundary.

    Caught inside the scope, the context manager exits cleanly and the run's telemetry is wrong.
    Not caught at all, the exception dies with the worker thread while the caller reads the
    end-of-stream sentinel and sees a clean finish. Both halves are asserted here because the
    old code did one of each: the ValueError handler sat inside the span, and everything else
    propagated past it and was lost.

    Measured before the fix, for the ValueError case: the exception reached the caller but no
    flow span was exported at all, because the consumer raises the moment it is queued, the
    generator is abandoned and the worker never finishes ending the span.
    """
    result = run_probe(mode)

    assert result["raised"] == expected_raised, result

    flow_spans = [s for s in result["spans"] if s["name"] == "flow.execute"]
    assert len(flow_spans) == 1, result["spans"]
    assert flow_spans[0]["status"] == "error", flow_spans[0]
    assert flow_spans[0]["error_type"] == expected_error_type, flow_spans[0]

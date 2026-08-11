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

    provider.force_flush()
    spans = [
        {"name": s.name, "span_id": s.context.span_id, "parent": s.parent.span_id if s.parent else None}
        for s in exporter.get_finished_spans()
    ]
    print("PROBE_RESULT " + json.dumps({"spans": spans, "inner_parent": inner_parent}))


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

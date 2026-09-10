"""Span *events* are the other carrier, and nothing asserted on them.

Every leak assertion in the suite serialises ``span.attributes``. Events are a separate place a
span can hold text, and the one that matters here is written by the SDK rather than by us:
``record_exception`` puts the exception message into an event. That is precisely why the flow
span opts out of it and sets ``error.type`` by hand.

An attributes-only assertion cannot see that. Delete ``record_exception=False`` from
``flow_execution_span`` and every existing test still passes while the exception message starts
reaching the operator's APM on every failed run.

Runs in a subprocess because the tracer provider is process-global.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from string import Template

import pytest

pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")

# The user's prompt. Present in the flow before anything fails, so a run that leaks inputs
# rather than errors is caught by the same sweep.
PROMPT = "SENTINELPROMPTQQQ"
# The component's own failure text, which is what record_exception would write into an event.
EXC_MESSAGE = "SENTINELCOMPONENTFAILUREQQQ"

PROBE_TEMPLATE = Template('''
import asyncio, json, os, sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom import Component
from lfx.graph import Graph
from lfx.io import MessageInput, Output
from lfx.observability import APPLICATION_TRACER_NAME
from lfx.schema.message import Message

MODE = sys.argv[1]


class Passthrough(Component):
    """Stands in for an LLM component: it sees the prompt and makes no network call."""

    display_name = "Passthrough"
    name = "Passthrough"
    inputs = [MessageInput(name="input_value", display_name="Input")]
    outputs = [Output(name="message", display_name="Message", method="respond")]

    def respond(self) -> Message:
        if MODE == "failure":
            raise RuntimeError("$EXC_MESSAGE")
        return self.input_value


def build():
    chat_input = ChatInput(_id="chat-input")
    chat_input.set(input_value="$PROMPT")
    middle = Passthrough(_id="passthrough")
    middle.set(input_value=chat_input.message_response)
    chat_output = ChatOutput(_id="chat-output")
    chat_output.set(input_value=middle.respond)
    return Graph(chat_input, chat_output, flow_id="11111111-1111-1111-1111-111111111111")


async def main():
    if MODE == "control":
        # Prove the dump below can see an event at all. Without this, "no events" reads the same
        # whether the boundary holds or the probe never looked.
        tracer = trace.get_tracer(APPLICATION_TRACER_NAME)
        with tracer.start_as_current_span("probe.control") as span:
            span.record_exception(RuntimeError("$EXC_MESSAGE"))
    else:
        graph = build()
        # arun, not async_start: async_start opens the span with make_current=False because it
        # is an async generator, and a span that is never made current never enters use_span, so
        # record_exception has nothing to act on there. arun makes it current, which is the path
        # where the argument under test actually applies.
        try:
            await graph.arun(inputs=[{"input_value": "$PROMPT"}], outputs=["chat-output"])
        except Exception:
            pass

    provider.force_flush()
    spans = [
        {
            "name": s.name,
            "scope": s.instrumentation_scope.name if s.instrumentation_scope else None,
            "attributes": {k: str(v) for k, v in (s.attributes or {}).items()},
            "events": [
                {"name": e.name, "attributes": {k: str(v) for k, v in (e.attributes or {}).items()}}
                for e in s.events
            ],
        }
        for s in exporter.get_finished_spans()
    ]
    print("PROBE_RESULT " + json.dumps(spans))


asyncio.run(main())
''')


def run_probe(mode: str) -> list[dict]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    source = PROBE_TEMPLATE.substitute(PROMPT=PROMPT, EXC_MESSAGE=EXC_MESSAGE)
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "probe.py"
        probe.write_text(source, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe), mode],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr
    lines = [ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT ")]
    assert lines, f"probe printed no result.\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    return json.loads(lines[0].removeprefix("PROBE_RESULT "))


def application_spans(spans: list[dict]) -> list[dict]:
    return [s for s in spans if s["scope"] == "langflow.observability"]


def test_a_successful_run_is_one_flow_span_and_no_component_spans():
    """The unit of work is the run. A per-component span would also carry component payloads."""
    spans = application_spans(run_probe("success"))

    assert [s["name"] for s in spans] == ["flow.execute"], [s["name"] for s in spans]


def test_the_prompt_reaches_neither_an_attribute_nor_an_event():
    """The flow carries a prompt before anything fails, so a run that leaks inputs is caught too."""
    spans = run_probe("success")

    # Asserted before the absence: an empty list satisfies "the sentinel is not in here", so
    # without this the check stops running the moment the probe stops producing spans, and stays
    # green while it does.
    assert [s for s in application_spans(spans) if s["name"] == "flow.execute"], spans

    assert PROMPT not in json.dumps(spans)


def test_a_failing_component_puts_its_message_in_no_event():
    """The regression this file exists for.

    ``record_exception`` writes the exception message into an event, so the flow span turns it
    off and reports ``error.type`` instead. Deleting that argument leaves every attribute-only
    assertion green while the message starts reaching the APM on every failed run.
    """
    spans = run_probe("failure")
    flow_spans = [s for s in application_spans(spans) if s["name"] == "flow.execute"]

    assert len(flow_spans) == 1, spans
    assert flow_spans[0]["attributes"].get("status") == "error", flow_spans[0]["attributes"]
    # The type is the whole point: it is what an operator gets instead of the message. arun wraps
    # the RuntimeError as ValueError("Error running graph: Error building Component Passthrough:
    # <the component's message>"), so telemetry must follow the exception cause without exporting
    # either message.
    assert flow_spans[0]["attributes"].get("error.type") == "RuntimeError"

    assert flow_spans[0]["events"] == [], flow_spans[0]["events"]
    assert EXC_MESSAGE not in json.dumps(spans)


def test_the_probe_would_have_seen_an_exception_event():
    """The control, because the assertions above are absences.

    A probe that never reads events produces the same empty list as a span that has none.
    """
    spans = run_probe("control")
    control = [s for s in spans if s["name"] == "probe.control"]

    assert control, spans
    assert control[0]["events"], "the probe cannot see span events at all"
    assert EXC_MESSAGE in json.dumps(control[0]["events"])

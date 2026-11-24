"""A stale span in the worker's context must not outrank the carrier on the job row.

``flow_execution_span`` turns an ended parent into a link, which is right when that parent is
the request this run came from. It is wrong when the ended span belongs to some *earlier*
request that the worker task happens to still be holding: the run then links to a request it
has nothing to do with, and a fabricated relationship renders in the APM as a real one, which
is worse than the orphan it replaced.

Reachable whenever the executor's worker tasks are first started from a request rather than at
lifespan, so they inherit that request's context permanently and every later run links back to
it. The carrier read off the job row is the authoritative answer for a queued run, so it wins
over any ended ambient span. A genuinely live parent still wins over both.
"""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry.sdk.trace")

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph
from lfx.observability import extract_trace_link, inject_trace_carrier, queued_trace_link

FLOW_ID = "33333333-3333-3333-3333-333333333333"


@pytest.fixture
def tracer_and_exporter():
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        processor = SimpleSpanProcessor(exporter)
        current.add_span_processor(processor)
        try:
            yield trace.get_tracer("test.worker"), exporter
        finally:
            processor.shutdown()
            exporter.clear()
        return

    provider = TracerProvider()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    try:
        yield trace.get_tracer("test.worker"), exporter
    finally:
        provider.shutdown()
        exporter.clear()


def build_graph() -> Graph:
    chat_input = ChatInput(_id="chat-input")
    chat_output = ChatOutput(_id="chat-output")
    chat_output.set(input_value=chat_input.message_response)
    return Graph(chat_input, chat_output, flow_id=FLOW_ID)


def _flow_links(exporter):
    spans = [s for s in exporter.get_finished_spans() if s.name == "flow.execute"]
    assert len(spans) == 1, [s.name for s in exporter.get_finished_spans()]
    return [link.context.trace_id for link in (spans[0].links or [])]


def test_the_carrier_beats_a_stale_ended_span_in_the_workers_context(tracer_and_exporter):
    """The regression. An older request's ended span must not capture this run."""
    from opentelemetry import trace

    tracer, exporter = tracer_and_exporter

    # The request that actually queued this job, whose context travelled on the job row.
    with tracer.start_as_current_span("originating.request") as originating:
        originating_trace = originating.get_span_context().trace_id
        carrier = inject_trace_carrier()

    # An unrelated, earlier request whose span the worker task is still holding, ended.
    stale = tracer.start_span("stale.earlier.request")
    stale.end()
    stale_trace = stale.get_span_context().trace_id
    assert stale_trace != originating_trace

    graph = build_graph()
    context = trace.set_span_in_context(stale)
    token = None
    from opentelemetry import context as otel_context

    token = otel_context.attach(context)
    try:
        with queued_trace_link(extract_trace_link(carrier)), graph.flow_execution_span():
            pass
    finally:
        otel_context.detach(token)

    links = _flow_links(exporter)
    assert links == [originating_trace], (
        f"linked to {[format(t, '032x') for t in links]}, "
        f"originating {format(originating_trace, '032x')}, stale {format(stale_trace, '032x')}"
    )


def test_a_live_parent_still_wins_over_the_carrier(tracer_and_exporter):
    """The control. A run nested inside a live request is a real child, not a link."""
    tracer, exporter = tracer_and_exporter

    with tracer.start_as_current_span("other.request") as other:
        carrier = inject_trace_carrier()
    link = extract_trace_link(carrier)

    graph = build_graph()
    with tracer.start_as_current_span("live.request") as live:
        live_trace = live.get_span_context().trace_id
        with queued_trace_link(link), graph.flow_execution_span():
            pass

    spans = [s for s in exporter.get_finished_spans() if s.name == "flow.execute"]
    assert len(spans) == 1
    # Still a real child of the live request, and no link stamped over it.
    assert spans[0].get_span_context().trace_id == live_trace
    assert spans[0].links in (None, ()), spans[0].links
    assert other.get_span_context().trace_id != live_trace

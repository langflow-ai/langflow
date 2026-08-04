"""The /build driver's application span, exercised through the real HTTP route.

The build driver walks the vertices itself and never enters ``Graph.arun`` / ``async_start`` /
``process``, so it did not inherit the flow span those three carry. That made the busiest
surfaces in the product — playground, v2 sync and background, voice — the ones the operator's
APM could not see. These tests drive the actual route so both halves are covered: the span the
build loop opens, and the protocol the route binds around it.
"""

from __future__ import annotations

import pytest
from lfx.observability import APPLICATION_TRACER_NAME

from tests.unit.build_utils import build_flow, consume_and_assert_stream, create_flow, get_build_events

pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture(scope="module")
def span_exporter():
    """Install a provider for this module and hand back its exporter.

    ``set_tracer_provider`` is process-global and first-write-wins, so the assert below is the
    point: if anything else in this worker installs a provider first, our spans go to it and
    every assertion here would pass vacuously. Failing loudly beats a green vacuous test.
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    assert trace.get_tracer_provider() is provider, (
        "another test installed a tracer provider first; these assertions would be vacuous"
    )
    return exporter


def _flow_spans(exporter):
    return [span for span in exporter.get_finished_spans() if span.name == "flow.execute"]


async def _run_a_playground_build(client, flow_data, headers) -> None:
    flow_id = await create_flow(client, flow_data, headers)
    build_response = await build_flow(client, flow_id, headers)
    job_id = build_response["job_id"]
    events_response = await get_build_events(client, job_id, headers)
    await consume_and_assert_stream(events_response, job_id)


async def test_the_playground_build_path_emits_exactly_one_flow_span(
    client, json_memory_chatbot_no_llm, logged_in_headers, span_exporter
):
    span_exporter.clear()

    await _run_a_playground_build(client, json_memory_chatbot_no_llm, logged_in_headers)

    spans = _flow_spans(span_exporter)
    assert len(spans) == 1, f"expected one flow span for one build, got {len(spans)}"
    span = spans[0]
    assert span.instrumentation_scope.name == APPLICATION_TRACER_NAME
    assert span.attributes["flow_id"]
    assert span.attributes["run_id"]
    assert span.attributes["status"] == "ok"


async def test_the_build_route_labels_the_run_as_the_playground(
    client, json_memory_chatbot_no_llm, logged_in_headers, span_exporter
):
    """The protocol is bound by the route, not the driver, so only a real request proves it."""
    span_exporter.clear()

    await _run_a_playground_build(client, json_memory_chatbot_no_llm, logged_in_headers)

    spans = _flow_spans(span_exporter)
    assert len(spans) == 1
    assert spans[0].attributes["protocol"] == "playground"


async def test_no_component_spans_reach_the_operators_apm(
    client, json_memory_chatbot_no_llm, logged_in_headers, span_exporter
):
    """One unit of work per run. A per-component span here would also carry component payloads."""
    span_exporter.clear()

    await _run_a_playground_build(client, json_memory_chatbot_no_llm, logged_in_headers)

    application_spans = [
        span
        for span in span_exporter.get_finished_spans()
        if span.instrumentation_scope.name == APPLICATION_TRACER_NAME
    ]
    assert [span.name for span in application_spans] == ["flow.execute"]

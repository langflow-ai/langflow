"""The /build driver's application span, exercised through the real HTTP route.

Note on naming: this drives POST /api/v1/build, which the canvas no longer calls (the frontend
moved to POST /api/v2/workflows). The driver underneath is shared, so this still covers it for
every surface that reaches it, but the protocol here is v1.build rather than playground. The
playground label is asserted on the v2 stream, where the IDE actually is.

The build driver walks the vertices itself and never enters ``Graph.arun`` / ``async_start`` /
``process``, so it did not inherit the flow span those three carry. That made the busiest
surfaces in the product — the v2 stream the canvas uses, v2 background, voice — the ones the
operator's APM could not see. (v2 sync goes through ``arun`` and always had one.)

These tests drive the actual route so both halves are covered: the span the build loop opens,
and the protocol the route binds around it.
"""

from __future__ import annotations

import json

import pytest
from lfx.observability import APPLICATION_TRACER_NAME

from tests.unit.build_utils import build_flow, consume_and_assert_stream, create_flow, get_build_events

pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture(scope="module")
def span_exporter():
    """Install a provider for this module and hand back its exporter.

    The sibling OTel tests run their provider in a subprocess because it is process-global.
    That is not available here: the point of these tests is the real HTTP route, which needs
    the app, the DB and the auth fixtures, so the provider has to go into the test process.

    Two consequences are handled rather than ignored. ``set_tracer_provider`` is
    first-write-wins, so the assert is what stops this file from passing vacuously if anything
    else in the worker installs one first. And the provider cannot be uninstalled, so the
    teardown shuts it down instead — otherwise every later test in this worker that runs a
    flow would keep appending spans to an exporter nobody reads.
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
    yield exporter
    provider.shutdown()
    exporter.clear()


def _flow_spans(exporter):
    return [span for span in exporter.get_finished_spans() if span.name == "flow.execute"]


async def _run_a_v1_build(client, flow_data, headers) -> None:
    flow_id = await create_flow(client, flow_data, headers)
    build_response = await build_flow(client, flow_id, headers)
    job_id = build_response["job_id"]
    events_response = await get_build_events(client, job_id, headers)
    await consume_and_assert_stream(events_response, job_id)


async def test_the_v1_build_path_emits_exactly_one_flow_span(
    client, json_memory_chatbot_no_llm, logged_in_headers, span_exporter
):
    span_exporter.clear()

    await _run_a_v1_build(client, json_memory_chatbot_no_llm, logged_in_headers)

    spans = _flow_spans(span_exporter)
    assert len(spans) == 1, f"expected one flow span for one build, got {len(spans)}"
    span = spans[0]
    assert span.instrumentation_scope.name == APPLICATION_TRACER_NAME
    assert span.attributes["flow_id"]
    assert span.attributes["run_id"]
    assert span.attributes["status"] == "ok"


async def test_the_build_route_labels_the_run_as_v1_build(
    client, json_memory_chatbot_no_llm, logged_in_headers, span_exporter
):
    """The protocol is bound by the route, not the driver, so only a real request proves it."""
    span_exporter.clear()

    await _run_a_v1_build(client, json_memory_chatbot_no_llm, logged_in_headers)

    spans = _flow_spans(span_exporter)
    assert len(spans) == 1
    assert spans[0].attributes["protocol"] == "v1.build"


async def test_no_component_spans_reach_the_operators_apm(
    client, json_memory_chatbot_no_llm, logged_in_headers, span_exporter
):
    """One unit of work per run. A per-component span here would also carry component payloads."""
    span_exporter.clear()

    await _run_a_v1_build(client, json_memory_chatbot_no_llm, logged_in_headers)

    application_spans = [
        span
        for span in span_exporter.get_finished_spans()
        if span.instrumentation_scope.name == APPLICATION_TRACER_NAME
    ]
    assert [span.name for span in application_spans] == ["flow.execute"]


# The build driver catches a component failure, turns it into an error output and stops walking,
# rather than raising. So the span sees a clean exit unless the driver tells it, and a failed run
# would report "ok" while the same flow through Graph.arun reports "error".
SENTINEL = "component-detail-that-must-not-be-exported"

FAILING_COMPONENT_CODE = f"""
from lfx.custom import Component
from lfx.io import HandleInput, Output, TabInput
from lfx.schema import Message


class TypeConverterComponent(Component):
    display_name = "Type Convert"
    description = "converts"
    name = "TypeConverterComponent"
    inputs = [
        HandleInput(name="input_data", display_name="Input", input_types=["Message", "Data", "DataFrame"]),
        TabInput(name="output_type", display_name="Output Type", options=["Message"], value="Message"),
    ]
    outputs = [Output(display_name="Message Output", name="message_output", method="convert_to_message")]

    def convert_to_message(self) -> Message:
        raise RuntimeError("{SENTINEL}")
"""


def _flow_with_a_failing_component(flow_data: str) -> str:
    payload = json.loads(flow_data)
    for node in payload["data"]["nodes"]:
        if node["id"] == "TypeConverterComponent-koSIz":
            node["data"]["node"]["template"]["code"]["value"] = FAILING_COMPONENT_CODE
    return json.dumps(payload)


async def test_a_failed_build_is_not_reported_as_a_successful_run(
    client, json_memory_chatbot_no_llm, logged_in_headers, span_exporter
):
    span_exporter.clear()

    flow_id = await create_flow(client, _flow_with_a_failing_component(json_memory_chatbot_no_llm), logged_in_headers)
    build_response = await build_flow(client, flow_id, logged_in_headers)
    events = await get_build_events(client, build_response["job_id"], logged_in_headers)
    body = "".join([line async for line in events.aiter_lines()])
    assert SENTINEL in body, "the component was supposed to fail this build"

    spans = _flow_spans(span_exporter)
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["status"] == "error"
    # The driver wraps the component's own exception, so this is the type an operator sees.
    assert span.attributes["error.type"] == "ComponentBuildError"
    # The wrapped message embeds component output, so only the type may reach the APM.
    assert SENTINEL not in json.dumps(dict(span.attributes))


async def test_a_declared_client_reaches_the_span(client, json_memory_chatbot_no_llm, logged_in_headers, span_exporter):
    span_exporter.clear()
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    build_response = await build_flow(client, flow_id, {**logged_in_headers, "x-langflow-client": "playground"})
    events = await get_build_events(client, build_response["job_id"], logged_in_headers)
    await consume_and_assert_stream(events, build_response["job_id"])

    spans = _flow_spans(span_exporter)
    assert len(spans) == 1
    assert spans[0].attributes["client"] == "playground"


async def test_an_unknown_client_is_dropped_rather_than_recorded(
    client, json_memory_chatbot_no_llm, logged_in_headers, span_exporter
):
    """A caller must not be able to mint span attribute values."""
    span_exporter.clear()
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    build_response = await build_flow(client, flow_id, {**logged_in_headers, "x-langflow-client": "not-a-real-client"})
    events = await get_build_events(client, build_response["job_id"], logged_in_headers)
    await consume_and_assert_stream(events, build_response["job_id"])

    spans = _flow_spans(span_exporter)
    assert len(spans) == 1
    assert "client" not in spans[0].attributes

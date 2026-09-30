"""A background run must be reachable from the request that queued it.

Before this, the two were unrelated traces. Measured on a real background run:

    flow.execute  trace_id = 1291125b0d1eaf83ea0508d451d160a9   <- its own trace
                  parent   = None
                  links    = []

An operator looking at a slow background run could not get back to the request that caused
it, and an operator looking at a slow request could not see the work it queued.

Driven through the real route rather than by calling the helpers, because the helpers already
have unit tests in ``src/lfx/tests/unit/test_trace_carrier.py``. What those cannot show is
that the carrier survives the actual hop: written on the job row by one request, read by the
runner that picks the job up afterwards.
"""

from __future__ import annotations

import asyncio

import pytest
from lfx.observability import APPLICATION_TRACER_NAME

pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture(scope="module")
def span_exporter():
    """Attach an exporter to whatever tracer provider this worker has, and hand it back.

    In-process rather than a subprocess because this needs the app, the database and the auth
    fixtures.

    Attaching rather than installing is deliberate. ``set_tracer_provider`` is
    first-write-wins, so a module that installs its own provider works alone and fails the
    moment xdist puts another provider-installing module in the same worker -- which is
    exactly what happened here on one Python version and not the others. Adding a processor
    to the provider that is already there has no such ordering dependency.

    The tests still cannot pass vacuously: each one asserts that its own spans arrived before
    asserting anything about their links.
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        # Someone already installed a real SDK provider. Ride it rather than fight it; the
        # helpers below filter to this module's own spans by name and scope.
        current.add_span_processor(processor)
        try:
            yield exporter
        finally:
            # Shut the processor down rather than detach it: a provider has no removal API,
            # so clearing the exporter empties the list and leaves the processor registered,
            # still appending every later span in this worker to it for the rest of the run.
            processor.shutdown()
            exporter.clear()
        return

    provider = TracerProvider()
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    try:
        yield exporter
    finally:
        provider.shutdown()
        exporter.clear()


def _flow_spans(exporter):
    return [
        s
        for s in exporter.get_finished_spans()
        if s.name == "flow.execute"
        and s.instrumentation_scope
        and s.instrumentation_scope.name == APPLICATION_TRACER_NAME
    ]


def _request_spans(exporter):
    return [s for s in exporter.get_finished_spans() if "workflows" in s.name and s.kind.name == "SERVER"]


async def _run_background(client, flow_id, api_key, exporter):
    """Start a background run and wait for its flow span to arrive."""
    response = await client.post(
        "/api/v2/workflows",
        headers={"x-api-key": api_key},
        json={"flow_id": str(flow_id), "input_value": "hello", "mode": "background"},
    )
    assert response.status_code == 200, response.text

    for _ in range(150):
        if _flow_spans(exporter):
            break
        await asyncio.sleep(0.1)
    return response.json()


async def test_a_background_run_links_back_to_the_request_that_queued_it(
    client, simple_api_test, created_api_key, span_exporter
):
    """The regression this file exists for."""
    span_exporter.clear()

    await _run_background(client, simple_api_test["id"], created_api_key.api_key, span_exporter)

    flows = _flow_spans(span_exporter)
    requests = _request_spans(span_exporter)

    # Asserted before the link check: with no spans at all, "the link is right" passes trivially.
    assert len(flows) == 1, [s.name for s in span_exporter.get_finished_spans()]
    assert requests, "no server span for the enqueuing request; the link has nothing to point at"

    links = [link.context.trace_id for link in (flows[0].links or [])]
    assert links == [requests[0].get_span_context().trace_id], (
        f"flow span links {[format(t, '032x') for t in links]}, "
        f"request trace {format(requests[0].get_span_context().trace_id, '032x')}"
    )


async def test_the_run_keeps_its_own_trace(client, simple_api_test, created_api_key, span_exporter):
    """A link, not a parent, and not a merge into the request's trace.

    The run starts after the request finished. Parenting it, or folding it into the same
    trace, renders as a child that begins after its parent ended.
    """
    span_exporter.clear()

    await _run_background(client, simple_api_test["id"], created_api_key.api_key, span_exporter)

    flow = _flow_spans(span_exporter)[0]
    request = _request_spans(span_exporter)[0]

    assert flow.parent is None, flow.parent
    assert flow.get_span_context().trace_id != request.get_span_context().trace_id


async def test_a_synchronous_run_gets_no_link(client, simple_api_test, created_api_key, span_exporter):
    """The control, and the thing that would break first if the carrier leaked.

    A sync run has a live request above it, so it is a real child and needs no link. If this
    grows one, the ambient link is escaping its binding and attaching to runs it has nothing
    to do with.
    """
    span_exporter.clear()

    response = await client.post(
        "/api/v2/workflows?mode=sync",
        headers={"x-api-key": created_api_key.api_key},
        json={"flow_id": str(simple_api_test["id"]), "input_value": "hello"},
    )
    assert response.status_code == 200, response.text

    flows = _flow_spans(span_exporter)
    assert flows, "no flow span for the sync run"
    assert all(not (s.links or []) for s in flows), [[link.context.trace_id for link in (s.links or [])] for s in flows]

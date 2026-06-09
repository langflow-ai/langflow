"""Test W3C trace context propagation behavior.

Tests cover:
- FastAPIInstrumentor inbound extraction
- Langflow-specific tracers inheriting extracted context via global OTel context
- Outbound httpx propagation with and without HTTPXClientInstrumentor
- Concurrent request isolation (no cross-request trace context leakage)
"""

from __future__ import annotations

import asyncio
import os
import threading
import uuid
from collections import defaultdict
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langflow.services.tracing.otlp import _reset_shared_provider
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


@pytest.fixture(autouse=True)
def _reset_otlp_provider():
    """Reset the shared OTLP TracerProvider before and after each test."""
    _reset_shared_provider()
    yield
    _reset_shared_provider()


class CollectingExporter(SpanExporter):
    """In-memory span exporter that collects finished spans for assertions."""

    def __init__(self):
        """Initialize with an empty span list and a lock for thread safety."""
        self.spans: list[Any] = []
        self._lock = threading.Lock()

    def export(self, spans):
        """Append finished spans to the internal list (thread-safe)."""
        with self._lock:
            self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        """No-op shutdown."""

    def force_flush(self, _timeout_millis=30000):
        """No-op flush; all spans are stored synchronously on export."""
        return True


@pytest.fixture
def otel_app():
    """Create a minimal FastAPI app instrumented the same way as main.py."""
    exporter = CollectingExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    app = FastAPI()

    @app.get("/health")
    async def health():
        """Minimal health endpoint for testing."""
        return {"status": "ok"}

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    yield app, exporter, provider

    FastAPIInstrumentor.uninstrument_app(app)
    provider.shutdown()


def test_traceparent_header_propagated(otel_app):
    """Server span inherits the trace-id and parent-span-id from an incoming traceparent header."""
    app, exporter, _provider = otel_app

    # Craft a known W3C traceparent: version-trace_id-parent_id-flags
    incoming_trace_id = "0af7651916cd43dd8448eb211c80319c"
    incoming_span_id = "b7ad6b7169203331"
    traceparent = f"00-{incoming_trace_id}-{incoming_span_id}-01"

    client = TestClient(app)
    response = client.get("/health", headers={"traceparent": traceparent})
    assert response.status_code == 200

    spans = exporter.spans
    assert len(spans) >= 1, "Expected at least one server span"

    # Find the root-most span in the trace (the one whose parent is the remote incoming span)
    matching = [s for s in spans if format(s.context.trace_id, "032x") == incoming_trace_id]
    assert matching, f"No spans found with trace_id {incoming_trace_id}"

    # The outermost span should have a remote parent matching the incoming span_id
    root_span = next(
        (s for s in matching if s.parent and s.parent.is_remote),
        None,
    )
    assert root_span is not None, (
        "Expected a span with a remote parent (from the incoming traceparent). "
        f"Span parents: {[(s.name, s.parent) for s in matching]}"
    )

    actual_parent_id = format(root_span.parent.span_id, "016x")
    assert actual_parent_id == incoming_span_id, (
        f"Root span parent_span_id {actual_parent_id} != incoming {incoming_span_id}"
    )


def test_no_traceparent_generates_new_trace(otel_app):
    """Without a traceparent header, the server span starts a fresh trace with no parent."""
    app, exporter, _provider = otel_app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200

    spans = exporter.spans
    assert len(spans) >= 1

    # Find the outermost span (no remote parent)
    root_spans = [s for s in spans if s.parent is None or not s.parent.is_remote]
    assert root_spans, "Expected at least one span without a remote parent"

    # None of the spans should have a remote parent
    remote_parent_spans = [s for s in spans if s.parent and s.parent.is_remote]
    assert not remote_parent_spans, "Expected no spans with remote parents when traceparent header is absent"


# ---------------------------------------------------------------------------
# Langflow-specific tracers inherit the FastAPI-extracted context
# ---------------------------------------------------------------------------


def test_otlp_tracer_root_span_inherits_active_context():
    """OTLPTracer root span inherits the active OTel context even with its own TracerProvider.

    OpenTelemetry's start_span() reads the global context (not the provider) to find a
    parent span. So when FastAPIInstrumentor has set an active span from an incoming
    traceparent header, the OTLPTracer's root span becomes a child of that span,
    sharing the same trace_id.
    """
    from langflow.services.tracing.otlp import OTLPTracer

    # Set up a "global" provider to simulate FastAPIInstrumentor's active span
    global_provider = TracerProvider(resource=Resource.create({"service.name": "global"}))
    global_provider.add_span_processor(SimpleSpanProcessor(CollectingExporter()))
    global_tracer = global_provider.get_tracer("test")

    # Simulate what FastAPIInstrumentor does: start a span and make it the active context
    fastapi_span = global_tracer.start_span("GET /api/v1/run/flow-id")
    ctx = trace.set_span_in_context(fastapi_span)
    token = otel_context.attach(ctx)

    try:
        with (
            patch.dict(
                os.environ,
                {
                    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
                },
                clear=True,
            ),
            patch(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
                return_value=CollectingExporter(),
            ),
        ):
            tracer = OTLPTracer(
                trace_name="test-flow - abc123",
                trace_type="chain",
                project_name="test-project",
                trace_id=uuid.uuid4(),
            )
            assert tracer.ready

        fastapi_trace_id = format(fastapi_span.get_span_context().trace_id, "032x")
        fastapi_span_id = format(fastapi_span.get_span_context().span_id, "016x")
        otlp_trace_id = format(tracer.root_span.context.trace_id, "032x")

        # The OTLPTracer root span shares the same trace_id as the FastAPI span
        assert otlp_trace_id == fastapi_trace_id, (
            f"OTLPTracer root span trace_id {otlp_trace_id} should match FastAPI span trace_id {fastapi_trace_id}"
        )

        # The OTLPTracer root span's parent is the FastAPI span
        assert tracer.root_span.parent is not None, "OTLPTracer root span should have a parent"
        actual_parent_id = format(tracer.root_span.parent.span_id, "016x")
        assert actual_parent_id == fastapi_span_id, (
            f"OTLPTracer root span parent {actual_parent_id} should be FastAPI span {fastapi_span_id}"
        )
    finally:
        otel_context.detach(token)
        fastapi_span.end()
        global_provider.shutdown()
        tracer.close()


def test_otlp_tracer_root_span_independent_without_active_context():
    """Without an active OTel context, the OTLPTracer root span starts an independent trace."""
    from langflow.services.tracing.otlp import OTLPTracer

    with (
        patch.dict(
            os.environ,
            {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
            },
            clear=True,
        ),
        patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            return_value=CollectingExporter(),
        ),
    ):
        tracer = OTLPTracer(
            trace_name="test-flow - abc123",
            trace_type="chain",
            project_name="test-project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready

    assert tracer.root_span.parent is None, "OTLPTracer root span should have no parent when no active context exists"
    tracer.close()


# ---------------------------------------------------------------------------
# Outbound httpx trace context propagation
# ---------------------------------------------------------------------------


def test_outbound_httpx_without_instrumentation_does_not_inject_traceparent(otel_app):
    """Without HTTPXClientInstrumentor, outbound httpx requests have no traceparent."""
    app, _exporter, _provider = otel_app
    captured_headers: dict[str, str] = {}

    @app.get("/call-external-uninstrumented")
    async def call_external():
        """Make an outbound httpx call using MockTransport (no instrumentation)."""

        async def capture_handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(capture_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await client.get("http://external-service.example.com/api/data")
        return {"status": "called"}

    incoming_trace_id = "0af7651916cd43dd8448eb211c80319c"
    incoming_span_id = "b7ad6b7169203331"
    traceparent = f"00-{incoming_trace_id}-{incoming_span_id}-01"

    client = TestClient(app)
    response = client.get("/call-external-uninstrumented", headers={"traceparent": traceparent})
    assert response.status_code == 200

    assert "traceparent" not in captured_headers, (
        "Outbound httpx request should NOT contain traceparent without instrumentation"
    )


def test_outbound_httpx_with_instrumentation_injects_traceparent(otel_app):
    """With HTTPXClientInstrumentor enabled, outbound httpx requests carry traceparent."""
    respx = pytest.importorskip("respx")
    otel_httpx = pytest.importorskip("opentelemetry.instrumentation.httpx")
    httpx_instrumentor_cls = otel_httpx.HTTPXClientInstrumentor

    app, _exporter, provider = otel_app
    captured_headers: dict[str, str] = {}

    httpx_instrumentor_cls().instrument(tracer_provider=provider)

    try:

        @app.get("/call-external-instrumented")
        async def call_external():
            """Make an outbound httpx call through respx mock (with instrumentation)."""
            with respx.mock:
                route = respx.get("http://external-service.example.com/api/data").mock(
                    return_value=httpx.Response(200, json={"ok": True})
                )
                async with httpx.AsyncClient() as client:
                    await client.get("http://external-service.example.com/api/data")
                # Capture the headers from the actual request that was sent
                captured_headers.update(dict(route.calls[0].request.headers))
            return {"status": "called"}

        incoming_trace_id = "0af7651916cd43dd8448eb211c80319c"
        incoming_span_id = "b7ad6b7169203331"
        traceparent = f"00-{incoming_trace_id}-{incoming_span_id}-01"

        client = TestClient(app)
        response = client.get("/call-external-instrumented", headers={"traceparent": traceparent})
        assert response.status_code == 200

        # The outbound httpx request should now have a traceparent header
        assert "traceparent" in captured_headers, (
            "Outbound httpx request should contain traceparent with HTTPXClientInstrumentor"
        )

        # The outbound traceparent should carry the same trace_id as the incoming one
        parts = captured_headers["traceparent"].split("-")
        assert parts[1] == incoming_trace_id, f"Outbound trace_id {parts[1]} should match incoming {incoming_trace_id}"
    finally:
        httpx_instrumentor_cls().uninstrument()


def test_manual_propagator_inject_works_inside_active_context(otel_app):
    """Manual TraceContextTextMapPropagator.inject() works inside an active span context."""
    app, _exporter, _provider = otel_app
    injected_carrier: dict[str, str] = {}

    @app.get("/manual-inject")
    async def manual_inject():
        propagator = TraceContextTextMapPropagator()
        propagator.inject(carrier=injected_carrier)
        return {"status": "injected"}

    incoming_trace_id = "0af7651916cd43dd8448eb211c80319c"
    incoming_span_id = "b7ad6b7169203331"
    traceparent = f"00-{incoming_trace_id}-{incoming_span_id}-01"

    client = TestClient(app)
    response = client.get("/manual-inject", headers={"traceparent": traceparent})
    assert response.status_code == 200

    assert "traceparent" in injected_carrier, "Manual propagator.inject() should produce a traceparent header"
    parts = injected_carrier["traceparent"].split("-")
    assert parts[1] == incoming_trace_id, f"Injected trace_id {parts[1]} should match incoming {incoming_trace_id}"


# ---------------------------------------------------------------------------
# Concurrent request isolation
# ---------------------------------------------------------------------------


def _make_trace_ids(n: int) -> list[tuple[str, str]]:
    """Generate n pairs of (trace_id, span_id) for use in traceparent headers."""
    return [(uuid.uuid4().hex, uuid.uuid4().hex[:16]) for _ in range(n)]


def test_concurrent_requests_have_isolated_trace_contexts():
    """Concurrent requests each carry their own traceparent; spans must not leak across requests.

    Sends multiple simultaneous requests with distinct trace-ids through an async
    endpoint that includes an asyncio.sleep (to force overlapping execution), then
    verifies every collected span belongs to exactly the trace-id that its request
    carried.
    """
    exporter = CollectingExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test-concurrent"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    app = FastAPI()

    # Barrier-style endpoint: all requests sleep so their handling overlaps
    @app.get("/slow")
    async def slow():
        await asyncio.sleep(0.05)
        return {"status": "ok"}

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    try:
        pairs = _make_trace_ids(10)

        # httpx.AsyncClient honours the ASGI transport and runs truly async
        async def _fire_all():
            """Send concurrent requests via ASGI transport and assert all succeed."""
            from httpx import ASGITransport, AsyncClient

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                tasks = [
                    client.get(
                        "/slow",
                        headers={"traceparent": f"00-{tid}-{sid}-01"},
                    )
                    for tid, sid in pairs
                ]
                responses = await asyncio.gather(*tasks)
                for r in responses:
                    assert r.status_code == 200

        asyncio.run(_fire_all())

        # Group finished spans by trace_id
        spans_by_trace: dict[str, list] = defaultdict(list)
        for span in exporter.spans:
            tid = format(span.context.trace_id, "032x")
            spans_by_trace[tid].append(span)

        expected_trace_ids = {tid for tid, _ in pairs}

        # Every span must belong to one of the incoming trace-ids
        for tid in spans_by_trace:
            assert tid in expected_trace_ids, f"Span with trace_id {tid} does not match any incoming traceparent"

        # Each incoming trace-id must have produced at least one span
        for tid, sid in pairs:
            assert tid in spans_by_trace, f"No spans found for incoming trace_id {tid}"
            # The outermost span for this trace must have a remote parent
            # whose span_id matches the incoming span_id
            root = next(
                (s for s in spans_by_trace[tid] if s.parent and s.parent.is_remote),
                None,
            )
            assert root is not None, f"Trace {tid} has no span with a remote parent"
            actual_parent = format(root.parent.span_id, "016x")
            assert actual_parent == sid, f"Trace {tid}: root span parent {actual_parent} != incoming span_id {sid}"
    finally:
        FastAPIInstrumentor.uninstrument_app(app)
        provider.shutdown()


def test_concurrent_otlp_tracers_have_isolated_contexts():
    """OTLPTracers created inside different active contexts get the correct parent.

    Simulates what happens when the tracing service initialises OTLPTracer
    instances for two concurrent requests, each with a different active span.
    """
    from langflow.services.tracing.otlp import OTLPTracer

    global_provider = TracerProvider(resource=Resource.create({"service.name": "global"}))
    global_provider.add_span_processor(SimpleSpanProcessor(CollectingExporter()))
    global_tracer = global_provider.get_tracer("test")

    results: dict[str, dict[str, str]] = {}
    barrier = threading.Barrier(2)

    def _create_tracer(label: str, parent_span) -> None:
        """Attach *parent_span* as active context and create an OTLPTracer, storing results."""
        ctx = trace.set_span_in_context(parent_span)
        token = otel_context.attach(ctx)
        try:
            # Wait until both threads have attached their context
            barrier.wait(timeout=5)

            tracer = OTLPTracer(
                trace_name=f"flow-{label}",
                trace_type="chain",
                project_name="test",
                trace_id=uuid.uuid4(),
            )
            assert tracer.ready

            results[label] = {
                "trace_id": format(tracer.root_span.context.trace_id, "032x"),
                "parent_span_id": format(tracer.root_span.parent.span_id, "016x") if tracer.root_span.parent else None,
            }
            tracer.close()
        finally:
            otel_context.detach(token)

    span_a = global_tracer.start_span("request-A")
    span_b = global_tracer.start_span("request-B")

    expected_a_trace = format(span_a.get_span_context().trace_id, "032x")
    expected_a_span = format(span_a.get_span_context().span_id, "016x")
    expected_b_trace = format(span_b.get_span_context().trace_id, "032x")
    expected_b_span = format(span_b.get_span_context().span_id, "016x")

    with (
        patch.dict(
            os.environ,
            {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"},
            clear=True,
        ),
        patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            side_effect=lambda *_args, **_kwargs: CollectingExporter(),
        ),
    ):
        t1 = threading.Thread(target=_create_tracer, args=("A", span_a))
        t2 = threading.Thread(target=_create_tracer, args=("B", span_b))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)
    assert not t1.is_alive()
    assert not t2.is_alive()

    span_a.end()
    span_b.end()
    global_provider.shutdown()

    assert results["A"]["trace_id"] == expected_a_trace, (
        f"Tracer A trace_id {results['A']['trace_id']} != expected {expected_a_trace}"
    )
    assert results["A"]["parent_span_id"] == expected_a_span, (
        f"Tracer A parent {results['A']['parent_span_id']} != expected {expected_a_span}"
    )
    assert results["B"]["trace_id"] == expected_b_trace, (
        f"Tracer B trace_id {results['B']['trace_id']} != expected {expected_b_trace}"
    )
    assert results["B"]["parent_span_id"] == expected_b_span, (
        f"Tracer B parent {results['B']['parent_span_id']} != expected {expected_b_span}"
    )

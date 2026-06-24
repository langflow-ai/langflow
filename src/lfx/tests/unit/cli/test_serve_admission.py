"""App-level tests for lfx serve admission control (429 paths + /metrics)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from lfx.cli.admission import BuildAdmissionConfig
from lfx.cli.serve_app import FlowMeta, FlowRegistry, create_multi_serve_app

pytestmark = pytest.mark.asyncio


def _registry_with_one_flow(monkeypatch=None):
    """Registry holding a single stub graph; execution is monkeypatched per test.

    When *monkeypatch* is supplied, also sets ``LANGFLOW_API_KEY`` so the
    ``verify_api_key`` dependency accepts requests with ``x-api-key: test``.
    """
    if monkeypatch is not None:
        monkeypatch.setenv("LANGFLOW_API_KEY", "test")  # pragma: allowlist secret
    registry = FlowRegistry()
    graph = SimpleNamespace()  # opaque; execute_graph_with_capture is patched out
    meta = FlowMeta(id="flow-1", relative_path="flow-1.json", title="flow-1", description=None)
    registry.add(graph, meta)
    return registry


async def test_metrics_endpoint_is_unauthenticated_and_exposes_gauges():
    registry = _registry_with_one_flow()
    app = create_multi_serve_app(
        registry=registry,
        admission_config=BuildAdmissionConfig(limit=2, timeout=1.0, profile="metrics-test"),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")  # no x-api-key header
    assert resp.status_code == 200
    body = resp.text
    assert "build_slots_limit" in body
    assert "build_slots_in_use" in body
    assert 'profile="metrics-test"' in body


async def test_metrics_endpoint_returns_503_when_prometheus_unavailable(monkeypatch):
    """Without the lfx[metrics] extra, /metrics reports 503 instead of crashing."""
    # The route reads the module-level flag at request time, so flip it there.
    monkeypatch.setattr("lfx.cli.serve_app.PROMETHEUS_AVAILABLE", False)
    registry = _registry_with_one_flow()
    app = create_multi_serve_app(
        registry=registry,
        admission_config=BuildAdmissionConfig(limit=1, timeout=1.0, profile="metrics-missing"),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 503
    assert "lfx[metrics]" in resp.text


async def test_run_returns_429_when_saturated(monkeypatch):
    registry = _registry_with_one_flow(monkeypatch)
    gate = asyncio.Event()  # holds the first request inside execution

    async def fake_execute(_graph, _input_value, session_id=None, user_id=None):  # noqa: ARG001
        await gate.wait()
        return [], ""

    # Patch the symbol as imported into serve_app, plus result extraction + validation.
    monkeypatch.setattr("lfx.cli.serve_app.execute_graph_with_capture", fake_execute)
    monkeypatch.setattr(
        "lfx.cli.serve_app.extract_result_data",
        lambda _results, _logs: {"success": True, "result": "ok"},
    )
    monkeypatch.setattr("lfx.cli.serve_app.validate_flow_for_current_settings", lambda _graph: None)

    app = create_multi_serve_app(
        registry=registry,
        admission_config=BuildAdmissionConfig(limit=1, timeout=0.2, profile="run-429"),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"x-api-key": "test"}
        # First request acquires the only slot and blocks inside fake_execute.
        first = asyncio.create_task(client.post("/flows/flow-1/run", json={"input_value": "hi"}, headers=headers))
        await asyncio.sleep(0.05)
        # Second request waits 0.2s for a slot, then 429s.
        second = await client.post("/flows/flow-1/run", json={"input_value": "hi"}, headers=headers)
        assert second.status_code == 429
        assert "Retry-After" in second.headers
        gate.set()  # let the first finish
        first_resp = await first
        assert first_resp.status_code == 200


async def test_stream_returns_429_when_saturated(monkeypatch):
    """A second streaming request must 429 when the only slot is held by the first."""
    registry = _registry_with_one_flow(monkeypatch)
    gate = asyncio.Event()  # blocks the first request inside gated_stream

    async def fake_consume(_queue, _consumed):  # mimics consume_and_yield signature
        await gate.wait()  # hold the slot until we release the gate
        yield "data: x\n\n"

    monkeypatch.setattr("lfx.cli.serve_app.consume_and_yield", fake_consume)
    monkeypatch.setattr("lfx.cli.serve_app.validate_flow_for_current_settings", lambda _graph: None)

    async def fake_generator(**_kwargs):
        return None

    monkeypatch.setattr("lfx.cli.serve_app.run_flow_generator_for_serve", fake_generator)

    app = create_multi_serve_app(
        registry=registry,
        admission_config=BuildAdmissionConfig(limit=1, timeout=0.2, profile="stream-429"),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"x-api-key": "test"}

        # Start the first request as a background task. With ASGITransport, client.post()
        # drives the full ASGI response — including consuming the StreamingResponse body —
        # so the task blocks in fake_consume's gate.wait(), which keeps the slot held
        # while the event loop is free for the second request.
        first = asyncio.create_task(client.post("/flows/flow-1/stream", json={"input_value": "hi"}, headers=headers))
        # Yield to the event loop so the first task runs far enough to enter fake_consume
        # and hit gate.wait() (and thereby hold the slot).
        await asyncio.sleep(0.05)

        # Second request must 429 — the only slot is still held by the first.
        second = await client.post("/flows/flow-1/stream", json={"input_value": "hi"}, headers=headers)
        assert second.status_code == 429
        assert "Retry-After" in second.headers

        # Release the gate so the first task can finish cleanly.
        gate.set()
        first_resp = await first
        assert first_resp.status_code == 200


async def test_stream_setup_error_releases_slot(monkeypatch):
    """A Phase-3 setup error after acquire() must release the slot (no leak)."""
    from lfx.cli.admission import BUILD_SLOTS_IN_USE

    registry = _registry_with_one_flow(monkeypatch)
    monkeypatch.setattr("lfx.cli.serve_app.validate_flow_for_current_settings", lambda _graph: None)

    # Force a failure inside Phase 3 (after acquire()) by making apply_global_vars_to_graph raise.
    # This is called after acquire() and deepcopy(), squarely inside the try/except that calls
    # release() on error.
    monkeypatch.setattr(
        "lfx.cli.serve_app.apply_global_vars_to_graph",
        lambda _graph, _vars: (_ for _ in ()).throw(RuntimeError("injected setup error")),
    )

    app = create_multi_serve_app(
        registry=registry,
        admission_config=BuildAdmissionConfig(limit=1, timeout=0.5, profile="stream-setuperr"),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/flows/flow-1/stream", json={"input_value": "hi"}, headers={"x-api-key": "test"})

    # The handler returns a 200 SSE error stream on setup failure — check the body.
    assert resp.status_code == 200
    assert "injected setup error" in resp.text

    # The slot must have been released — in_use back to 0.
    assert BUILD_SLOTS_IN_USE.labels(profile="stream-setuperr")._value.get() == 0

    # A follow-up request can still acquire (no permanent slot leak).
    async def fake_consume(_queue, _consumed):
        yield "data: ok\n\n"

    monkeypatch.setattr("lfx.cli.serve_app.consume_and_yield", fake_consume)

    async def fake_generator(**_kwargs):
        return None

    monkeypatch.setattr("lfx.cli.serve_app.run_flow_generator_for_serve", fake_generator)
    # Restore apply_global_vars_to_graph to a no-op for the follow-up request.
    monkeypatch.setattr("lfx.cli.serve_app.apply_global_vars_to_graph", lambda _graph, _vars: None)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        follow_up = await client.post("/flows/flow-1/stream", json={"input_value": "hi"}, headers={"x-api-key": "test"})
    assert follow_up.status_code == 200
    assert BUILD_SLOTS_IN_USE.labels(profile="stream-setuperr")._value.get() == 0


async def test_stream_releases_slot_after_completion(monkeypatch):
    """A completed stream must return its slot so in_use returns to 0."""
    from lfx.cli.admission import BUILD_SLOTS_IN_USE

    registry = _registry_with_one_flow(monkeypatch)
    monkeypatch.setattr("lfx.cli.serve_app.validate_flow_for_current_settings", lambda _graph: None)

    async def fake_consume(_queue, _consumed):  # mimics consume_and_yield
        # At this point the slot should be held by the streaming handler
        assert BUILD_SLOTS_IN_USE.labels(profile="stream-rel")._value.get() == 1
        yield "data: one\n\n"
        yield "data: two\n\n"

    monkeypatch.setattr("lfx.cli.serve_app.consume_and_yield", fake_consume)

    # Avoid real graph execution task setup:
    async def fake_generator(**_kwargs):
        return None

    monkeypatch.setattr("lfx.cli.serve_app.run_flow_generator_for_serve", fake_generator)

    app = create_multi_serve_app(
        registry=registry,
        admission_config=BuildAdmissionConfig(limit=1, timeout=0.5, profile="stream-rel"),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/flows/flow-1/stream", json={"input_value": "hi"}, headers={"x-api-key": "test"})
        assert resp.status_code == 200
        _ = resp.text  # drain the stream to completion
    assert BUILD_SLOTS_IN_USE.labels(profile="stream-rel")._value.get() == 0


async def test_stream_releases_slot_on_client_disconnect(monkeypatch):
    """A client disconnecting mid-stream must release the held slot (in_use → 0).

    Mechanism: we call the route handler directly to obtain the StreamingResponse
    object, start consuming its body_iterator (asserting the slot is held), then
    call ``await body_iterator.aclose()`` — this is exactly what Starlette/Uvicorn
    does when a client disconnects — and assert the slot is released.

    We prefer this over the httpx ASGITransport approach because ASGITransport
    buffers the full response before returning, making it impossible to force an
    early close at a controlled mid-stream point in a deterministic way. The
    body_iterator approach is deterministic and directly exercises the gated_stream
    ``finally`` block that owns the release() call.
    """
    from lfx.cli.admission import BUILD_SLOTS_IN_USE
    from lfx.cli.serve_app import StreamRequest
    from starlette.responses import StreamingResponse

    profile = "stream-disc"

    monkeypatch.setattr("lfx.cli.serve_app.validate_flow_for_current_settings", lambda _graph: None)

    # Must be a coroutine function: serve_app calls asyncio.create_task(run_flow_generator_for_serve(...))
    async def fake_generator(**_kwargs):
        return None

    monkeypatch.setattr("lfx.cli.serve_app.run_flow_generator_for_serve", fake_generator)

    # A consumer that yields one chunk then blocks indefinitely — simulates a
    # long-running stream that will be interrupted by a client disconnect.
    async def fake_consume(_queue, _consumed):
        yield "data: first\n\n"
        # Block until cancelled (i.e. until the generator is aclose()'d)
        await asyncio.sleep(3600)

    monkeypatch.setattr("lfx.cli.serve_app.consume_and_yield", fake_consume)

    registry = _registry_with_one_flow(monkeypatch)
    app = create_multi_serve_app(
        registry=registry,
        admission_config=BuildAdmissionConfig(limit=1, timeout=5.0, profile=profile),
    )

    # Find and invoke the route handler directly to get a StreamingResponse without
    # going through HTTP — this lets us drive body_iterator ourselves.
    stream_route = None
    for route in app.routes:
        if hasattr(route, "path") and "/stream" in route.path:
            stream_route = route
            break

    assert stream_route is not None, "Could not find /stream route"

    srequest = StreamRequest(input_value="hi")
    response = await stream_route.endpoint(flow_id="flow-1", request=srequest, user_id=None)

    assert isinstance(response, StreamingResponse)

    # Begin iterating: read the first chunk to confirm the slot is held.
    body_iterator = response.body_iterator
    first_chunk = await body_iterator.__anext__()
    assert first_chunk  # got data back

    # Slot must be held at this point (acquire() ran, in_use incremented).
    assert BUILD_SLOTS_IN_USE.labels(profile=profile)._value.get() == 1

    # Simulate client disconnect: aclose() is exactly what Starlette/Uvicorn calls
    # on disconnect, which throws GeneratorExit into the async generator, triggering
    # the gated_stream finally block that owns the release() call.
    await body_iterator.aclose()

    # The gated_stream finally block must have run, releasing the slot.
    assert BUILD_SLOTS_IN_USE.labels(profile=profile)._value.get() == 0

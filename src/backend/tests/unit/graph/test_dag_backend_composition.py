"""Dependency-ready lifetime composition with the actual native DB tracer."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.tracing.native import NativeTracer
from langflow.services.tracing.service import TracingService, trace_context_var
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import HandleInput, Output
from lfx.schema.message import Message
from sqlmodel import select


async def _await_run(task, timeout: float):
    """Await a run task under a hard bound that cancellation suppression cannot extend.

    asyncio.wait never cancels the task, so the bound holds even if the run's
    drain keeps suppressing cancellation (the regression class covered here).
    """
    done, _pending = await asyncio.wait({task}, timeout=timeout)
    if not done:
        task.cancel()
        await asyncio.wait({task}, timeout=5)
        pytest.fail(f"graph run did not finish within {timeout}s")
    return await task


class NativeNode(Component):
    supports_dependency_ready_scheduling = True
    inputs = [HandleInput(name="messages", input_types=["Message"], is_list=True)]
    outputs = [Output(name="message", method="message_response")]

    async def message_response(self) -> Message:
        if self.__dict__.get("_self_cancel"):
            raise asyncio.CancelledError
        if entered := self.__dict__.get("_build_entered"):
            entered.set()
            await self._build_release.wait()
        return Message(text="materialized")


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["success", "cancel_flush", "cancel_build", "self_cancel", "partial_startup"])
async def test_native_worker_and_database_flush_complete_before_return(async_session, monkeypatch, phase):
    service = TracingService(SimpleNamespace(settings=SimpleNamespace(deactivate_tracing=False)))
    # Disable optional vendor integrations only. NativeTracer and its SQL flush
    # remain real, backed by the repository's local async_session fixture.
    for name in ("langsmith", "langwatch", "langfuse", "arize_phoenix", "opik", "traceloop", "openlayer"):
        monkeypatch.setattr(service, f"_initialize_{name}_tracer", lambda _context: None)
    monkeypatch.setenv("LANGFLOW_NATIVE_TRACING", "true")
    monkeypatch.setattr("lfx.services.deps.get_tracing_service", lambda: service)
    monkeypatch.setattr("lfx.graph.graph.base.get_tracing_service", lambda: service)
    entered, release = asyncio.Event(), asyncio.Event()
    committed, flushed, contexts = [], [], []

    @asynccontextmanager
    async def local_session_scope():
        entered.set()
        await release.wait()
        yield async_session
        await async_session.commit()
        committed.append(True)

    monkeypatch.setattr("lfx.services.deps.session_scope", local_session_scope)
    original_wait = NativeTracer.wait_for_flush

    async def wait_for_flush(self):
        await original_wait(self)
        flushed.append(self)

    monkeypatch.setattr(NativeTracer, "wait_for_flush", wait_for_flush)
    original_start = service.start_tracers

    async def start(**kwargs):
        await original_start(**kwargs)
        contexts.append(trace_context_var.get())
        if phase == "partial_startup":
            msg = "partial native startup"
            raise RuntimeError(msg)

    monkeypatch.setattr(service, "start_tracers", start)
    source, target = NativeNode(_id="source"), NativeNode(_id="target")
    build_entered, build_release = asyncio.Event(), asyncio.Event()
    if phase == "cancel_build":
        source._build_entered, source._build_release = build_entered, build_release
    if phase == "self_cancel":
        source._self_cancel = True
    target.set(messages=[source.message_response])
    flow = Flow(id=uuid4(), name="native-dag")
    async_session.add(flow)
    await async_session.commit()
    graph = Graph(source, target, flow_id=str(flow.id))
    # Flow-level vertex-build persistence is a different store; keep this test
    # scoped to native traces and use an explicit named transport double.
    graph.persist_messages = False

    async def event_transport(**_kwargs):
        return None

    monkeypatch.setattr("lfx.graph.utils.emit_vertex_build_event", event_transport)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    try:
        if phase == "cancel_build":
            await asyncio.wait_for(build_entered.wait(), 5)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            # Cancellation reaches the in-flight build promptly (default-path
            # parity). The run is still unfinished here: unwinding plus
            # end_all_traces cannot complete within two loop turns, and the
            # shared DB-session gate below then holds run-level finalization
            # until released.
            assert not task.done()
            build_release.set()
        await asyncio.wait_for(entered.wait(), 5)
        assert not task.done()
        assert committed == []
        if phase == "cancel_flush":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
    finally:
        release.set()
    if phase in {"cancel_flush", "cancel_build", "self_cancel"}:
        with pytest.raises(asyncio.CancelledError):
            await _await_run(task, 10)
    elif phase == "partial_startup":
        with pytest.raises(RuntimeError, match="partial native startup"):
            await _await_run(task, 10)
    else:
        await _await_run(task, 10)
    assert committed == [True]
    assert len(flushed) == 1
    tracer = flushed[0]
    assert tracer._flush_task.done()
    assert contexts[0].worker_task is None
    assert contexts[0].traces_queue.empty()
    traces = (await async_session.exec(select(TraceTable).where(TraceTable.id == UUID(graph._run_id)))).all()
    spans = (await async_session.exec(select(SpanTable).where(SpanTable.trace_id == UUID(graph._run_id)))).all()
    assert len(traces) == 1
    expected_spans = 0 if phase == "partial_startup" else (1 if phase in {"self_cancel", "cancel_build"} else 2)
    assert len(spans) == expected_spans
    assert all(span.end_time is not None for span in spans)
    assert tracer.spans == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["normal", "slow", "exception"])
async def test_actual_webhook_manager_payload_and_helper_error_contract(monkeypatch, transport):
    from langflow.services.event_manager import WebhookEventManager

    manager = WebhookEventManager()
    monkeypatch.setattr("langflow.services.event_manager.webhook_event_manager", manager)
    source, target = NativeNode(_id="source"), NativeNode(_id="target")
    target.set(messages=[source.message_response])
    flow_id = str(uuid4())
    graph = Graph(source, target, flow_id=flow_id)
    graph.persist_messages = False
    queue = await manager.subscribe(flow_id)
    entered, release = asyncio.Event(), asyncio.Event()
    original_emit, build = manager.emit, graph.build_vertex
    builds, debug = [], []

    async def controlled(vertex_id, **kwargs):
        builds.append(vertex_id)
        return await build(vertex_id=vertex_id, **kwargs)

    # This is an explicitly named transport fault/latency double around the real
    # manager, not a replacement for emit_vertex_build_event.
    async def fault_transport(flow_id, event_type, data):
        if event_type == "end_vertex" and data["build_data"]["id"] == "source":
            entered.set()
            if transport == "slow":
                await release.wait()
            if transport == "exception":
                msg = "test transport failure"
                raise RuntimeError(msg)
        await original_emit(flow_id, event_type, data)

    monkeypatch.setattr(manager, "emit", fault_transport)
    monkeypatch.setattr(graph, "build_vertex", controlled)
    monkeypatch.setattr("lfx.graph.utils.logger.debug", lambda *args, **_kwargs: debug.append(args))
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        if transport == "slow":
            assert builds == ["source"]
            assert not task.done()
        release.set()
        await _await_run(task, 10)
        assert builds == ["source", "target"]
        emitted = []
        while not queue.empty():
            item = queue.get_nowait()
            if item["event"] == "end_vertex":
                emitted.append(item["data"]["build_data"])
        assert [item["id"] for item in emitted] == (["target"] if transport == "exception" else ["source", "target"])
        assert any(str(item[0]).startswith("SSE emission failed") for item in debug) is (transport == "exception")
        for item in emitted:
            assert set(item) == {
                "id",
                "valid",
                "params",
                "data",
                "artifacts",
                "timestamp",
                "messages",
                "inactivated_vertices",
                "next_vertices_ids",
                "top_level_vertices",
            }
            assert set(item["data"]) == {"results", "outputs", "logs", "messages", "duration"}
            assert item["next_vertices_ids"] == (["target"] if item["id"] == "source" else [])
            assert item["inactivated_vertices"] == []
    finally:
        release.set()
        await manager.unsubscribe(flow_id, queue)

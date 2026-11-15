# ruff: noqa: ARG001, TRY003, EM101
import asyncio

import pytest

from tests.unit.graph.graph._dag_components import branched


@pytest.mark.asyncio
async def test_outer_cancel_naturally_drains_admitted_tasks(monkeypatch):
    graph = branched()
    build = graph.build_vertex
    entered = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()
    calls = []

    async def controlled(vertex_id, **kwargs):
        calls.append(vertex_id)
        if vertex_id == "slow":
            entered.set()
            try:
                await release.wait()
            finally:
                finished.set()
        return await build(vertex_id=vertex_id, **kwargs)

    monkeypatch.setattr(graph, "build_vertex", controlled)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    await asyncio.wait_for(entered.wait(), 3)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    assert not finished.is_set()
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()
    assert "merge" not in calls


@pytest.mark.asyncio
async def test_arun_finalizer_once_after_outputs_and_no_graph_context(monkeypatch):
    from lfx.execution import set_default_coordinator

    set_default_coordinator(None)
    graph = branched()
    calls = []
    output = graph.vertex_map["merge"]

    async def consume():
        calls.append("output")

    async def end(outputs=None, error=None):
        calls.append(("end", error))

    build = graph.build_vertex

    async def cleared(vertex_id, **kwargs):
        result = await build(vertex_id=vertex_id, **kwargs)
        if vertex_id == "merge":
            result.vertex.result = None
        return result

    monkeypatch.setattr(graph, "build_vertex", cleared)
    monkeypatch.setattr(output, "consume_async_generator", consume, raising=False)
    monkeypatch.setattr(graph, "end_all_traces", end)
    await graph.arun(inputs=[{}], outputs=["merge"], dag_max_concurrency=2)
    await asyncio.sleep(0)
    assert calls == ["output", ("end", None)]
    assert not any("dag" in key for key in graph.__dict__)
    assert not any("dag" in key for key in graph.__getstate__())


@pytest.mark.asyncio
async def test_arun_finalization_cannot_be_abandoned_by_repeated_cancel(monkeypatch):
    from lfx.execution import set_default_coordinator

    set_default_coordinator(None)
    graph = branched()
    entered = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()
    calls = []

    async def end(outputs=None, error=None):
        calls.append(error)
        entered.set()
        await release.wait()
        finished.set()

    monkeypatch.setattr(graph, "end_all_traces", end)
    task = asyncio.create_task(graph.arun(inputs=[{}], dag_max_concurrency=2))
    await asyncio.wait_for(entered.wait(), 3)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()
    assert calls == [None]


@pytest.mark.asyncio
async def test_arun_output_failure_still_awaits_finalizer(monkeypatch):
    from lfx.execution import set_default_coordinator

    set_default_coordinator(None)
    graph = branched()
    calls = []

    async def consume():
        raise LookupError("output failed")

    async def end(outputs=None, error=None):
        calls.append(error)

    build = graph.build_vertex

    async def cleared(vertex_id, **kwargs):
        result = await build(vertex_id=vertex_id, **kwargs)
        if vertex_id == "merge":
            result.vertex.result = None
        return result

    monkeypatch.setattr(graph, "build_vertex", cleared)
    monkeypatch.setattr(graph.vertex_map["merge"], "consume_async_generator", consume, raising=False)
    monkeypatch.setattr(graph, "end_all_traces", end)
    with pytest.raises(LookupError, match="output failed"):
        await graph.arun(inputs=[{}], dag_max_concurrency=2)
    assert len(calls) == 1
    assert isinstance(calls[0], LookupError)


@pytest.mark.asyncio
async def test_initialization_partial_failure_ends_once(monkeypatch):
    graph = branched()
    calls = []

    async def initialize():
        raise RuntimeError("partially initialized")

    async def end(outputs=None, error=None):
        calls.append(error)

    monkeypatch.setattr(graph, "initialize_run", initialize)
    monkeypatch.setattr(graph, "end_all_traces", end)
    with pytest.raises(RuntimeError, match="partially initialized"):
        await graph.process(fallback_to_env_vars=False, dag_max_concurrency=2)
    assert len(calls) == 1
    assert isinstance(calls[0], RuntimeError)


@pytest.mark.asyncio
async def test_real_sync_component_output_thread_drains_before_cancel_returns():
    import threading

    from lfx.graph import Graph

    from tests.unit.graph.graph._dag_components import StaticNode, ThreadNode

    source, target = ThreadNode(_id="source"), StaticNode(_id="target")
    source._entered, source._release, source._finished = (threading.Event() for _ in range(3))
    target.set(messages=[source.message_response])
    graph = Graph(source, target)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    try:
        assert await asyncio.to_thread(source._entered.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert not source._finished.is_set()
    finally:
        source._release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert source._finished.is_set()
    assert not graph.vertex_map["target"].built


@pytest.mark.asyncio
@pytest.mark.parametrize("first", ["cancel", "failure"])
async def test_first_observed_outcome_wins_while_draining(first, monkeypatch):
    graph = branched()
    build = graph.build_vertex
    both = asyncio.Event()
    fail = asyncio.Event()
    release = asyncio.Event()
    calls = []
    final = []

    async def controlled(vertex_id, **kwargs):
        calls.append(vertex_id)
        if vertex_id == "slow":
            both.set()
            await release.wait()
        if vertex_id == "fast":
            await both.wait()
            await fail.wait()
            raise LookupError("branch failed")
        return await build(vertex_id=vertex_id, **kwargs)

    async def end(outputs=None, error=None):
        final.append(error)

    monkeypatch.setattr(graph, "build_vertex", controlled)
    monkeypatch.setattr(graph, "end_all_traces", end)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    await asyncio.wait_for(both.wait(), 3)
    if first == "cancel":
        task.cancel()
        await asyncio.sleep(0)
        fail.set()
    else:
        fail.set()
        # Observe drainage through the latched native finalization later. Give the
        # scheduler a turn to observe the completed failure before cancelling.
        for _ in range(8):
            await asyncio.sleep(0)
        task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    expected = asyncio.CancelledError if first == "cancel" else LookupError
    with pytest.raises(expected):
        await task
    assert len(final) == 1
    assert isinstance(final[0], expected)
    assert "merge" not in calls


@pytest.mark.asyncio
async def test_selected_self_cancel_drains_sibling_and_finalizes_run(monkeypatch):
    graph = branched()
    build = graph.build_vertex
    release = asyncio.Event()
    cancelled = asyncio.Event()
    drained = []
    final = []

    async def controlled(vertex_id, **kwargs):
        if vertex_id == "slow":
            await release.wait()
            drained.append(vertex_id)
        if vertex_id == "fast":
            cancelled.set()
            raise asyncio.CancelledError
        return await build(vertex_id=vertex_id, **kwargs)

    async def end(outputs=None, error=None):
        final.append(error)

    monkeypatch.setattr(graph, "build_vertex", controlled)
    monkeypatch.setattr(graph, "end_all_traces", end)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    await asyncio.wait_for(cancelled.wait(), 3)
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert drained == ["slow"]
    assert len(final) == 1
    assert isinstance(final[0], asyncio.CancelledError)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["persist", "emit"])
async def test_cancel_during_completion_handling_drains_without_admitting_child(phase, monkeypatch):
    graph = branched()
    release = asyncio.Event()
    entered = asyncio.Event()
    build = graph.build_vertex
    calls = []
    final = []

    async def controlled(vertex_id, **kwargs):
        calls.append(vertex_id)
        if vertex_id == "slow":
            await release.wait()
        return await build(vertex_id=vertex_id, **kwargs)

    async def handling(result, *args):
        if result.vertex.id == "fast":
            entered.set()
            await release.wait()

    async def end(outputs=None, error=None):
        final.append(error)

    monkeypatch.setattr(graph, "build_vertex", controlled)
    monkeypatch.setattr(
        graph, "_record_vertex_build_result" if phase == "persist" else "_emit_vertex_build_result", handling
    )
    monkeypatch.setattr(graph, "end_all_traces", end)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    await asyncio.wait_for(entered.wait(), 3)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "child" not in calls
    assert "merge" not in calls
    assert len(final) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
async def test_cleanup_error_propagates_on_success_but_not_over_primary(monkeypatch, fail):
    graph = branched()
    build = graph.build_vertex
    calls = []

    async def controlled(vertex_id, **kwargs):
        if fail and vertex_id == "source":
            raise LookupError("primary")
        return await build(vertex_id=vertex_id, **kwargs)

    async def end(outputs=None, error=None):
        calls.append(error)
        raise RuntimeError("cleanup")

    monkeypatch.setattr(graph, "build_vertex", controlled)
    monkeypatch.setattr(graph, "end_all_traces", end)
    with pytest.raises(LookupError if fail else RuntimeError, match="primary" if fail else "cleanup"):
        await graph.process(fallback_to_env_vars=False, dag_max_concurrency=2)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_subgraph_keeps_parent_trace_ownership(monkeypatch):
    graph = branched()
    graph._is_subgraph = True

    async def forbidden(**kwargs):
        pytest.fail("subgraph finalized parent traces")

    monkeypatch.setattr(graph, "end_all_traces", forbidden)
    await graph.process(fallback_to_env_vars=False, dag_max_concurrency=2)


@pytest.mark.asyncio
async def test_unexpected_iterator_output_stops_without_legacy_rerun(monkeypatch):
    from lfx.graph import Graph

    from tests.unit.graph.graph._dag_components import IteratorNode, StaticNode

    source, target = IteratorNode(_id="source"), StaticNode(_id="target")
    target.set(messages=[source.message_response])
    graph = Graph(source, target)
    calls = []

    async def forbidden(*args, **kwargs):
        pytest.fail("partial execution fell back")

    async def end(outputs=None, error=None):
        calls.append(error)

    monkeypatch.setattr(graph, "_execute_tasks", forbidden)
    monkeypatch.setattr(graph, "end_all_traces", end)
    with pytest.raises(TypeError, match="materialized"):
        await graph.process(fallback_to_env_vars=False, dag_max_concurrency=2)
    assert not graph.vertex_map["target"].built
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_standalone_event_import_error_is_bare_pass(monkeypatch):
    import builtins

    from lfx.graph.utils import emit_vertex_build_event

    actual_import = builtins.__import__
    debug = []

    def without_backend(name, *args, **kwargs):
        if name == "langflow.services.event_manager":
            raise ImportError
        return actual_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_backend)
    monkeypatch.setattr("lfx.graph.utils.logger.debug", lambda *args, **_kwargs: debug.append(args))
    await emit_vertex_build_event(flow_id="flow", vertex_id="vertex", valid=True, params={}, data_dict={})
    assert debug == []


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["persist", "emit"])
@pytest.mark.parametrize("outcome", ["error", "self_cancel"])
async def test_completed_sibling_failure_during_handler_stops_admission(phase, outcome, monkeypatch):
    graph = branched()
    original = graph.build_vertex
    in_handler, fail, failed, release = (asyncio.Event() for _ in range(4))
    calls = []
    error = LookupError("sibling failed during completion handler")

    async def build(vertex_id, **kwargs):
        calls.append(vertex_id)
        if vertex_id == "slow":
            await fail.wait()
            failed.set()
            if outcome == "self_cancel":
                raise asyncio.CancelledError
            raise error
        return await original(vertex_id=vertex_id, **kwargs)

    async def handler(result, *args):
        if result.vertex.id == "fast":
            in_handler.set()
            await release.wait()

    monkeypatch.setattr(graph, "build_vertex", build)
    monkeypatch.setattr(
        graph, "_record_vertex_build_result" if phase == "persist" else "_emit_vertex_build_result", handler
    )
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    try:
        await asyncio.wait_for(in_handler.wait(), 3)
        fail.set()
        await asyncio.wait_for(failed.wait(), 3)
        # The sibling task finishes while the owner remains inside the handler.
        await asyncio.sleep(0)
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError if outcome == "self_cancel" else LookupError):
        await task
    assert "child" not in calls
    assert "merge" not in calls


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["persist", "emit"])
async def test_outer_cancel_observed_inside_handler_precedes_unharvested_error(phase, monkeypatch):
    graph = branched()
    original = graph.build_vertex
    in_handler, fail, failed, release = (asyncio.Event() for _ in range(4))
    calls = []

    async def build(vertex_id, **kwargs):
        calls.append(vertex_id)
        if vertex_id == "slow":
            await fail.wait()
            failed.set()
            raise LookupError("not yet observed by scheduler")
        return await original(vertex_id=vertex_id, **kwargs)

    async def handler(result, *args):
        if result.vertex.id == "fast":
            in_handler.set()
            await release.wait()

    monkeypatch.setattr(graph, "build_vertex", build)
    monkeypatch.setattr(
        graph, "_record_vertex_build_result" if phase == "persist" else "_emit_vertex_build_result", handler
    )
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    try:
        await asyncio.wait_for(in_handler.wait(), 3)
        fail.set()
        await asyncio.wait_for(failed.wait(), 3)
        await asyncio.sleep(0)
        task.cancel()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "child" not in calls


@pytest.mark.asyncio
async def test_reharvest_repeats_when_each_handler_completes_another_sibling(monkeypatch):
    from lfx.graph import Graph

    from tests.unit.graph.graph._dag_components import StaticNode

    source, a, b, c, d, child, merge = [StaticNode(_id=key) for key in ("source", "a", "b", "c", "d", "child", "merge")]
    for node in (a, b, c, d):
        node.set(messages=[source.message_response])
    child.set(messages=[a.message_response])
    merge.set(messages=[child.message_response, b.message_response, c.message_response, d.message_response])
    graph = Graph(source, merge)
    original = graph.build_vertex
    release = {key: asyncio.Event() for key in ("b", "c", "d")}
    finished = {key: asyncio.Event() for key in ("b", "c", "d")}
    calls, handled = [], []
    error = LookupError("fourth branch failed during third handler")

    async def build(vertex_id, **kwargs):
        calls.append(vertex_id)
        if vertex_id in release:
            await release[vertex_id].wait()
        try:
            if vertex_id == "d":
                raise error
            return await original(vertex_id=vertex_id, **kwargs)
        finally:
            if vertex_id in finished:
                finished[vertex_id].set()

    async def record(result):
        vertex_id = result.vertex.id
        handled.append(vertex_id)
        next_id = {"a": "b", "b": "c", "c": "d"}.get(vertex_id)
        if next_id:
            release[next_id].set()
            await asyncio.wait_for(finished[next_id].wait(), 3)
            await asyncio.sleep(0)

    monkeypatch.setattr(graph, "build_vertex", build)
    monkeypatch.setattr(graph, "_record_vertex_build_result", record)
    with pytest.raises(LookupError) as caught:
        await graph.process(fallback_to_env_vars=False, dag_max_concurrency=4)
    assert caught.value is error
    assert handled == ["source", "a", "b", "c"]
    assert "child" not in calls
    assert "merge" not in calls


@pytest.mark.asyncio
async def test_completed_failure_group_uses_graph_order_not_finish_order(monkeypatch):
    graph = branched()
    original = graph.build_vertex
    in_handler, release_handler = asyncio.Event(), asyncio.Event()
    release_slow, release_fast = asyncio.Event(), asyncio.Event()
    finished_slow, finished_fast = asyncio.Event(), asyncio.Event()
    errors = {key: LookupError(key) for key in ("slow", "fast")}
    expected = next(vertex.id for vertex in graph.vertices if vertex.id in errors)
    reverse = [key for key in reversed([vertex.id for vertex in graph.vertices]) if key in errors]

    async def build(vertex_id, **kwargs):
        if vertex_id in errors:
            await {"slow": release_slow, "fast": release_fast}[vertex_id].wait()
            {"slow": finished_slow, "fast": finished_fast}[vertex_id].set()
            raise errors[vertex_id]
        return await original(vertex_id=vertex_id, **kwargs)

    # Hold asyncio.wait's observation until both failures are completed, rather
    # than relying on incidental event-loop timing to form the completed group.
    import lfx.graph.graph.dag_scheduler as scheduler

    original_wait = asyncio.wait

    async def wait(pending, **kwargs):
        if len(pending) == 2:
            in_handler.set()
            await release_handler.wait()
        return await original_wait(pending, **kwargs)

    monkeypatch.setattr(graph, "build_vertex", build)
    monkeypatch.setattr(scheduler.asyncio, "wait", wait)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    try:
        await asyncio.wait_for(in_handler.wait(), 3)
        for key in reverse:
            {"slow": release_slow, "fast": release_fast}[key].set()
            await asyncio.wait_for({"slow": finished_slow, "fast": finished_fast}[key].wait(), 3)
            await asyncio.sleep(0)
    finally:
        release_handler.set()
    with pytest.raises(LookupError) as caught:
        await task
    assert caught.value is errors[expected]

# ruff: noqa: ARG001, TRY003, EM101
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.unit.graph.graph._dag_components import branched


async def _await_run(awaitable, timeout: float):
    """Await a graph run under a hard bound that cancellation suppression cannot extend.

    asyncio.wait_for cancels the awaiting frame; a run whose drain keeps
    suppressing cancellation (the regression class these tests guard) would
    hold CI forever. asyncio.wait never cancels the task, so the bound holds.
    """
    task = asyncio.ensure_future(awaitable)
    done, _pending = await asyncio.wait({task}, timeout=timeout)
    if not done:
        task.cancel()
        # Best-effort bounded drain so the suite does not leak the stuck task.
        # asyncio.wait never raises the task's own exception; a cancellation of
        # the test itself must propagate, so nothing is suppressed here.
        await asyncio.wait({task}, timeout=5)
        pytest.fail(f"graph run did not finish within {timeout}s")
    return await task


@pytest.mark.asyncio
async def test_outer_cancel_cancels_admitted_tasks(monkeypatch):
    graph = branched()
    build = graph.build_vertex
    entered = asyncio.Event()
    release = asyncio.Event()
    cancelled = asyncio.Event()
    calls = []

    async def controlled(vertex_id, **kwargs):
        calls.append(vertex_id)
        if vertex_id == "slow":
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
        return await build(vertex_id=vertex_id, **kwargs)

    monkeypatch.setattr(graph, "build_vertex", controlled)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        # Cancellation reaches the admitted in-flight build, matching the
        # default path, instead of waiting for it to finish naturally.
        await asyncio.wait_for(cancelled.wait(), 3)
        with pytest.raises(asyncio.CancelledError):
            await _await_run(task, 10)
        assert not release.is_set()
        assert "merge" not in calls
    finally:
        release.set()


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
        await _await_run(task, 10)
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
        await _await_run(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2), 15)
    assert len(calls) == 1
    assert isinstance(calls[0], RuntimeError)


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["outer_cancel", "sibling_failure"])
async def test_run_waits_for_sync_thread_before_raising(trigger, monkeypatch):
    import threading

    from lfx.graph import Graph

    from tests.unit.graph.graph._dag_components import StaticNode, ThreadNode

    source, fast, target = [StaticNode(_id=key) for key in ("source", "fast", "target")]
    slow = ThreadNode(_id="slow")
    slow._entered, slow._release, slow._finished = (threading.Event() for _ in range(3))
    slow.set(messages=[source.message_response])
    fast.set(messages=[source.message_response])
    target.set(messages=[slow.message_response, fast.message_response])
    graph = Graph(source, target)
    build = graph.build_vertex
    failing = asyncio.Event()
    error = LookupError("sibling failure")

    async def controlled(vertex_id, **kwargs):
        if vertex_id == "fast" and trigger == "sibling_failure":
            assert await asyncio.to_thread(slow._entered.wait, 3)
            failing.set()
            raise error
        return await build(vertex_id=vertex_id, **kwargs)

    monkeypatch.setattr(graph, "build_vertex", controlled)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    try:
        if trigger == "outer_cancel":
            assert await asyncio.to_thread(slow._entered.wait, 3)
            task.cancel()
        else:
            await asyncio.wait_for(failing.wait(), 3)
        done, _pending = await asyncio.wait({task}, timeout=0.5)
        assert not done
    finally:
        slow._release.set()
        expected = asyncio.CancelledError if trigger == "outer_cancel" else LookupError
        with pytest.raises(expected) as caught:
            await _await_run(task, 10)
    if trigger == "sibling_failure":
        assert caught.value is error
    assert slow._finished.is_set()
    assert not graph.vertex_map["target"].built


@pytest.mark.asyncio
@pytest.mark.parametrize("first", ["cancel", "failure"])
async def test_first_observed_outcome_wins_while_draining(first, monkeypatch):
    graph = branched()
    build = graph.build_vertex
    both = asyncio.Event()
    fail = asyncio.Event()
    unwinding = asyncio.Event()
    unwind_release = asyncio.Event()
    calls = []
    final = []

    async def controlled(vertex_id, **kwargs):
        calls.append(vertex_id)
        if vertex_id == "slow":
            both.set()
            try:
                await asyncio.Event().wait()  # parked until cancelled
            except asyncio.CancelledError:
                # Hold the unwind open so the second outcome lands mid-drain.
                unwinding.set()
                await unwind_release.wait()
                raise
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
    try:
        await asyncio.wait_for(both.wait(), 3)
        if first == "cancel":
            # One synchronous stretch, no await between: the failure completes
            # while the scheduler is parked in asyncio.wait with _must_cancel
            # set, so the outer cancel is observed first and the failure is
            # only ever consumed by the drain's gather(return_exceptions=True).
            fail.set()
            task.cancel()
        else:
            fail.set()
            # The scheduler latches the failure, cancels the admitted sibling,
            # and parks in the held drain unwind.
            await asyncio.wait_for(unwinding.wait(), 3)
            # A repeated outer cancel mid-unwind is absorbed by _await_owned
            # (the drain future is not done), so it cannot replace the primary.
            task.cancel()
        await asyncio.wait_for(unwinding.wait(), 3)
        unwind_release.set()
        expected = asyncio.CancelledError if first == "cancel" else LookupError
        with pytest.raises(expected):
            await _await_run(task, 10)
        assert len(final) == 1
        assert isinstance(final[0], expected)
        assert "merge" not in calls
    finally:
        unwind_release.set()


@pytest.mark.asyncio
async def test_selected_self_cancel_cancels_sibling_and_finalizes_run(monkeypatch):
    graph = branched()
    build = graph.build_vertex
    release = asyncio.Event()
    cancelled = asyncio.Event()
    sibling_cancelled = asyncio.Event()
    final = []

    async def controlled(vertex_id, **kwargs):
        if vertex_id == "slow":
            try:
                await release.wait()
            except asyncio.CancelledError:
                sibling_cancelled.set()
                raise
        if vertex_id == "fast":
            cancelled.set()
            raise asyncio.CancelledError
        return await build(vertex_id=vertex_id, **kwargs)

    async def end(outputs=None, error=None):
        final.append(error)

    monkeypatch.setattr(graph, "build_vertex", controlled)
    monkeypatch.setattr(graph, "end_all_traces", end)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    try:
        await asyncio.wait_for(cancelled.wait(), 3)
        # The self-cancelled vertex cancels its admitted sibling instead of
        # draining it to natural completion.
        await asyncio.wait_for(sibling_cancelled.wait(), 3)
        with pytest.raises(asyncio.CancelledError):
            await _await_run(task, 10)
        assert not release.is_set()
        assert len(final) == 1
        assert isinstance(final[0], asyncio.CancelledError)
    finally:
        release.set()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["persist", "emit"])
async def test_cancel_during_completion_handling_cancels_without_admitting_child(phase, monkeypatch):
    graph = branched()
    release = asyncio.Event()
    entered = asyncio.Event()
    cancelled = asyncio.Event()
    build = graph.build_vertex
    calls = []
    final = []

    async def controlled(vertex_id, **kwargs):
        calls.append(vertex_id)
        if vertex_id == "slow":
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
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
    try:
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        # Cancellation unwinds the handler and cancels the admitted "slow"
        # build instead of waiting for it; no descendant is admitted.
        with pytest.raises(asyncio.CancelledError):
            await _await_run(task, 10)
        assert cancelled.is_set()
        assert "child" not in calls
        assert "merge" not in calls
        assert len(final) == 1
    finally:
        release.set()


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
        await _await_run(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2), 15)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_subgraph_keeps_parent_trace_ownership(monkeypatch):
    graph = branched()
    graph._is_subgraph = True

    async def forbidden(**kwargs):
        pytest.fail("subgraph finalized parent traces")

    monkeypatch.setattr(graph, "end_all_traces", forbidden)
    await _await_run(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2), 15)


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
        await _await_run(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2), 15)
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
        await _await_run(task, 10)
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
        await _await_run(task, 10)
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
        await _await_run(graph.process(fallback_to_env_vars=False, dag_max_concurrency=4), 15)
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
        await _await_run(task, 10)
    assert caught.value is errors[expected]


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["outer_cancel", "sibling_failure", "webhook_failure"])
async def test_run_returns_only_after_admitted_unwind_completes(trigger, monkeypatch):
    webhook_start = "webhook-source" if trigger == "webhook_failure" else None
    graph = branched(webhook_start or "source")
    build = graph.build_vertex
    entered = asyncio.Event()
    build_release = asyncio.Event()
    unwind_started = asyncio.Event()
    unwind_release = asyncio.Event()
    unwind_finished = asyncio.Event()
    log_started = asyncio.Event()
    log_release = asyncio.Event()
    error = LookupError("fast failed")

    async def controlled(vertex_id, **kwargs):
        if vertex_id == "slow":
            entered.set()
            try:
                await build_release.wait()
            except asyncio.CancelledError:
                # Hold the unwind open: the run must not return before it ends.
                unwind_started.set()
                await unwind_release.wait()
                unwind_finished.set()
                raise
        if vertex_id == "fast":
            await entered.wait()
            if trigger != "outer_cancel":
                raise error
        return await build(vertex_id=vertex_id, **kwargs)

    async def log_failure(vertex_id, result):
        assert vertex_id == "fast"
        assert result is error
        log_started.set()
        await log_release.wait()

    monkeypatch.setattr(graph, "build_vertex", controlled)
    monkeypatch.setattr(graph, "_log_vertex_build_from_exception", log_failure)
    task = asyncio.create_task(
        graph.process(fallback_to_env_vars=False, dag_max_concurrency=2, start_component_id=webhook_start)
    )
    try:
        await asyncio.wait_for(entered.wait(), 3)
        if trigger == "outer_cancel":
            task.cancel()
        if webhook_start:
            await asyncio.wait_for(log_started.wait(), 3)
        await asyncio.wait_for(unwind_started.wait(), 3)
        log_release.set()
        # After logging finishes, the sibling's unwind must still hold up the
        # run. Cancelling it again would interrupt cleanup and end the run.
        done, _pending = await asyncio.wait({task}, timeout=0.5)
        assert not done
        unwind_release.set()
        expected = asyncio.CancelledError if trigger == "outer_cancel" else LookupError
        with pytest.raises(expected):
            await _await_run(task, 10)
        # The admitted sibling finished unwinding before the run returned.
        assert unwind_finished.is_set()
    finally:
        log_release.set()
        build_release.set()
        unwind_release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancelled_first_in_graph_order_beats_completed_group_failure(monkeypatch):
    graph = branched()
    original = graph.build_vertex
    in_handler, release_handler = asyncio.Event(), asyncio.Event()
    calls = []
    error = LookupError("sibling failed in the same completed group")
    cancelled_id, failed_id = [vertex.id for vertex in graph.vertices if vertex.id in ("slow", "fast")]
    released = {key: asyncio.Event() for key in (cancelled_id, failed_id)}
    finished = {key: asyncio.Event() for key in (cancelled_id, failed_id)}

    async def build(vertex_id, **kwargs):
        calls.append(vertex_id)
        if vertex_id == cancelled_id:
            await released[vertex_id].wait()
            finished[vertex_id].set()
            raise asyncio.CancelledError
        if vertex_id == failed_id:
            await released[vertex_id].wait()
            finished[vertex_id].set()
            raise error
        return await original(vertex_id=vertex_id, **kwargs)

    # Hold asyncio.wait's observation until both siblings are completed, so the
    # cancelled and the failed task land in the same harvest group.
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
        # Complete them in reverse graph order; the graph-order-first cancelled
        # sibling must still win over the later failure.
        for key in (failed_id, cancelled_id):
            released[key].set()
            await asyncio.wait_for(finished[key].wait(), 3)
            await asyncio.sleep(0)
    finally:
        release_handler.set()
    with pytest.raises(asyncio.CancelledError):
        await _await_run(task, 10)
    assert "child" not in calls
    assert "merge" not in calls


@pytest.mark.asyncio
async def test_failure_cancels_in_flight_sibling(monkeypatch):
    graph = branched()
    build = graph.build_vertex
    entered = asyncio.Event()
    release = asyncio.Event()
    sibling_cancelled = asyncio.Event()
    calls = []
    error = LookupError("fast failed")

    async def controlled(vertex_id, **kwargs):
        calls.append(vertex_id)
        if vertex_id == "slow":
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                sibling_cancelled.set()
                raise
        if vertex_id == "fast":
            await entered.wait()
            raise error
        return await build(vertex_id=vertex_id, **kwargs)

    monkeypatch.setattr(graph, "build_vertex", controlled)
    try:
        # The first failure cancels the admitted sibling instead of letting it
        # run to completion. The default path lets same-layer siblings finish
        # naturally on failure; this path cancels the admitted siblings.
        with pytest.raises(LookupError, match="fast failed"):
            await _await_run(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2), 10)
        assert sibling_cancelled.is_set()
        assert "child" not in calls
        assert "merge" not in calls
    finally:
        release.set()


@pytest.mark.asyncio
async def test_ineligible_graph_logs_debug_and_uses_default_path(monkeypatch):
    from lfx.custom.custom_component.component import Component
    from lfx.graph import Graph
    from lfx.io import HandleInput, Output
    from lfx.schema.message import Message

    class NoPromiseNode(Component):
        inputs = [HandleInput(name="messages", input_types=["Message"], is_list=True)]
        outputs = [Output(name="message", method="message_response")]

        async def message_response(self) -> Message:
            return Message(text="plain")

    source, target = NoPromiseNode(_id="source"), NoPromiseNode(_id="target")
    target.set(messages=[source.message_response])
    graph = Graph(source, target)

    logger_mock = MagicMock()
    for method in ("adebug", "ainfo", "awarning", "aerror", "aexception", "acritical"):
        setattr(logger_mock, method, AsyncMock())
    monkeypatch.setattr("lfx.graph.graph.base.logger", logger_mock)

    # The expected reason comes from the actual eligibility check, computed
    # before the run changes graph state (afterwards it would read
    # "previously built vertex").
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate

    reason = inspect_dag_candidate(graph)
    assert isinstance(reason, str)
    await _await_run(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2), 15)
    debug_messages = [str(call.args[0]) for call in logger_mock.adebug.await_args_list]
    fallback_logs = [m for m in debug_messages if "Dependency-ready scheduling ineligible" in m]
    assert fallback_logs == [f"Dependency-ready scheduling ineligible ({reason}); using the default path."]
    # The default path still ran the graph.
    assert graph.vertex_map["source"].built
    assert graph.vertex_map["target"].built

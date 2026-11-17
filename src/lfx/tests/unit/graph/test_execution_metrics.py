"""Local statistics never take ownership of graph execution or tracing."""

import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.graph import metrics as module
from lfx.services.database.service import NoopDatabaseService


def graph():
    source = ChatInput(_id="source").set(input_value="hello metrics", should_store_message=False)
    sink = ChatOutput(_id="sink").set(input_value=source.message_response, should_store_message=False)
    return Graph(source, sink, flow_name="local")


async def test_real_graph_and_copy_lifecycle():
    target = graph()
    with patch("lfx.services.deps.get_db_service", return_value=NoopDatabaseService()):
        with target.collect_execution_metrics() as metrics:
            with pytest.raises(RuntimeError, match="already active"), target.collect_execution_metrics():
                pass
            assert metrics.snapshot()["nodes"] == {}
            assert copy.deepcopy(target)._execution_metrics is None
            assert target.copy_for_run(user_id=None)._execution_metrics is None
            _ = [r async for r in target.async_start()]
        data = metrics.snapshot()
        assert list(data["nodes"]) == ["sink", "source"]
        assert all(n["call_count"] == n["returned_count"] == 1 for n in data["nodes"].values())
        assert target._execution_metrics is None
        data["nodes"].clear()
        assert len(metrics.snapshot()["nodes"]) == 2


async def test_clock_aggregates_midrun_and_late_completion(monkeypatch):
    target = graph()
    monkeypatch.setattr(module, "_clock", iter([0.0, 1.0, 2.0, 4.0, 5.0, 8.0]).__next__)
    with target.collect_execution_metrics() as metrics:
        first = metrics._begin("source")
        assert metrics.snapshot()["nodes"] == {}
        metrics._finish("source", first, "returned")
        late = metrics._begin("source")
    frozen = metrics.snapshot()
    assert frozen["incomplete"] is True
    assert frozen["nodes"]["source"]["total_duration_seconds"] == 3.0
    before = dict(metrics.__dict__)
    # A later scope cannot receive this earlier call's observation.
    monkeypatch.setattr(module, "_clock", lambda: 10.0)
    with target.collect_execution_metrics() as newer:
        metrics._finish("source", late, "returned")
        assert newer.snapshot()["nodes"] == {}
    assert metrics.__dict__ == before


@pytest.mark.parametrize("outcome", ["returned", "raised", "cancelled"])
async def test_all_terminal_buckets_and_duplicate_names(monkeypatch, outcome):
    target = SimpleNamespace(
        vertices=[SimpleNamespace(id="a", display_name="Same"), SimpleNamespace(id="b", display_name="Same")],
        flow_id=None,
        flow_name=None,
    )
    monkeypatch.setattr(module, "_clock", lambda: 2.0)
    with module.collect_execution_metrics(target) as metrics:
        for key in ["a", "b", "a"]:
            metrics._finish(key, metrics._begin(key), outcome)
        assert metrics._begin("unknown") is None
    rows = metrics.snapshot()["nodes"]
    assert list(rows) == ["a", "b"]
    assert rows["a"]["call_count"] == rows["a"][outcome + "_count"] == 2
    assert rows["b"]["call_count"] == 1
    assert rows["a"]["total_duration_seconds"] == 0.0


async def test_foreign_calls_skip_and_active_snapshot_rejects():
    target = graph()
    with target.collect_execution_metrics() as metrics:

        async def foreign():
            assert metrics._begin("source") is None
            with pytest.raises(RuntimeError, match="owner loop"):
                metrics.snapshot()

        await asyncio.to_thread(lambda: asyncio.run(foreign()))
        assert metrics.snapshot()["nodes"] == {}
        assert metrics.snapshot()["incomplete"] is False
    assert await asyncio.to_thread(metrics.snapshot) == metrics.snapshot()


async def test_record_fault_and_clock_anomaly_do_not_escape(monkeypatch):
    target = graph()
    with target.collect_execution_metrics() as metrics:
        begin = metrics._begin("source")
        monkeypatch.setattr(metrics, "_record", lambda *_args: (_ for _ in ()).throw(RuntimeError("diagnostic")))
        metrics._finish("source", begin, "returned")
        assert metrics._inflight == 0
        assert metrics.snapshot()["incomplete"] is True
    assert metrics.snapshot()["nodes"] == {}
    for invalid in [-1.0, float("nan"), float("inf")]:
        monkeypatch.setattr(module, "_clock", lambda: 0.0)
        with target.collect_execution_metrics() as metrics:
            begin = metrics._begin("source")
            monkeypatch.setattr(module, "_clock", lambda invalid=invalid: invalid)
            metrics._finish("source", begin, "raised")
            assert metrics.snapshot()["incomplete"] is True
            assert metrics.snapshot()["nodes"] == {}


async def test_disabled_has_no_clock_calls_and_invalid_ids_do_not_allocate(monkeypatch):
    target = graph()
    monkeypatch.setattr(module, "_clock", lambda: (_ for _ in ()).throw(AssertionError("clock disabled")))
    with patch("lfx.services.deps.get_db_service", return_value=NoopDatabaseService()):
        _ = [r async for r in target.async_start()]
    monkeypatch.setattr(module, "_clock", lambda: 0.0)
    with target.collect_execution_metrics() as metrics, pytest.raises(ValueError, match="not-a-vertex"):
        await target.build_vertex("not-a-vertex")
    assert metrics.snapshot()["nodes"] == {}


async def test_missing_result_is_raised_and_original_exception_preserved(monkeypatch):
    target = Graph()
    vertex = SimpleNamespace(id="x", display_name="x", frozen=False, is_loop=False, result=None)

    async def build(**_kwargs):
        return None

    vertex.build = build
    target.vertices = [vertex]
    monkeypatch.setattr(target, "get_vertex", lambda _key: vertex)
    with target.collect_execution_metrics() as metrics, pytest.raises(ValueError, match="no result"):
        await target.build_vertex("x")
    assert metrics.snapshot()["nodes"]["x"]["raised_count"] == 1


async def test_scope_setup_fault_leaves_graph_disabled(monkeypatch):
    target = graph()
    monkeypatch.setattr(module, "_clock", lambda: (_ for _ in ()).throw(RuntimeError("bad clock")))
    with pytest.raises(RuntimeError, match="bad clock"), target.collect_execution_metrics():
        pass
    assert target._execution_metrics is None


@pytest.mark.parametrize("error", [RuntimeError("build error"), asyncio.CancelledError(), SystemExit(13)])
async def test_original_exception_survives_diagnostic_fault(monkeypatch, error):
    target = Graph()
    vertex = SimpleNamespace(id="x", display_name="x", frozen=False, is_loop=False, result=None)

    async def build(**_kwargs):
        raise error

    vertex.build = build
    target.vertices = [vertex]
    monkeypatch.setattr(target, "get_vertex", lambda _key: vertex)
    with target.collect_execution_metrics() as metrics:
        monkeypatch.setattr(metrics, "_record", lambda *_args: (_ for _ in ()).throw(RuntimeError("record fault")))
        with pytest.raises(type(error)) as caught:
            await target.build_vertex("x")
        assert caught.value is error
    assert metrics.snapshot()["incomplete"] is True


async def test_control_flow_diagnostic_not_swallowed_without_primary(monkeypatch):
    target = graph()
    error = KeyboardInterrupt()
    with target.collect_execution_metrics() as metrics:
        start = metrics._begin("source")
        monkeypatch.setattr(metrics, "_record", lambda *_args: (_ for _ in ()).throw(error))
        with pytest.raises(KeyboardInterrupt) as caught:
            metrics._finish("source", start, "returned")
        assert caught.value is error


async def test_exit_while_graph_generator_suspended_freezes_report():
    target = graph()
    with patch("lfx.services.deps.get_db_service", return_value=NoopDatabaseService()):
        stream = target.async_start()
        with target.collect_execution_metrics() as metrics:
            await anext(stream)
        before = metrics.snapshot()
        await stream.aclose()
    assert metrics.snapshot() == before
    assert target._execution_metrics is None


async def test_foreign_exit_rejected_without_mutating_owner():
    target = graph()
    context = target.collect_execution_metrics()
    metrics = context.__enter__()
    try:

        async def foreign():
            with pytest.raises(RuntimeError, match="scope exit"):
                metrics._close()

        await asyncio.to_thread(lambda: asyncio.run(foreign()))
        assert metrics._active
        assert target._execution_metrics is metrics
    finally:
        context.__exit__(None, None, None)
    assert not metrics._active


def test_scope_requires_async_owner():
    target = graph()
    with pytest.raises(RuntimeError, match="running event loop"), target.collect_execution_metrics():
        pass
    assert target._execution_metrics is None


async def test_real_parallel_builds_are_independent_and_cancel_propagates(monkeypatch):
    target = Graph()
    for key in ["a", "b"]:
        target.add_component(ChatInput(_id=key).set(input_value=key, should_store_message=False), key)
    target.prepare()
    entered = [asyncio.Event(), asyncio.Event()]
    release = asyncio.Event()
    for index, key in enumerate(["a", "b"]):
        vertex = target.get_vertex(key)
        original = vertex.build

        async def wait_build(*args, _index=index, _original=original, **kwargs):
            entered[_index].set()
            await release.wait()
            return await _original(*args, **kwargs)

        monkeypatch.setattr(vertex, "build", wait_build)
    with (
        patch("lfx.services.deps.get_db_service", return_value=NoopDatabaseService()),
        target.collect_execution_metrics() as metrics,
    ):
        tasks = [asyncio.create_task(target.build_vertex(key)) for key in ["a", "b"]]
        await asyncio.wait_for(asyncio.gather(*(signal.wait() for signal in entered)), 5)
        assert metrics.snapshot()["nodes"] == {}
        tasks[0].cancel()
        release.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert isinstance(results[0], asyncio.CancelledError)
        assert results[1].vertex.id == "b"
    nodes = metrics.snapshot()["nodes"]
    assert nodes["a"]["cancelled_count"] == 1
    assert nodes["b"]["returned_count"] == 1


async def test_real_checkpoint_resume_records_only_new_calls():
    from lfx.graph.checkpoint.store import InMemoryCheckpointStore
    from lfx.graph.exceptions import GraphPausedException

    target = graph()
    target.session_id = "metrics-checkpoint"
    target.set_run_id()
    target.checkpointing_enabled = True
    target.job_id = "metrics-checkpoint"
    target.checkpoint_store = InMemoryCheckpointStore()
    with patch("lfx.services.deps.get_db_service", return_value=NoopDatabaseService()):
        with target.collect_execution_metrics() as first:
            await target.astep()
            checkpoint = target.build_checkpoint()
            target.request_pause()
            with pytest.raises(GraphPausedException):
                await target.process(fallback_to_env_vars=False)
        assert list(first.snapshot()["nodes"]) == ["source"]
        restored = Graph.resume_from_checkpoint(checkpoint)
        assert restored._execution_metrics is None
        with restored.collect_execution_metrics() as second:
            await restored.process(fallback_to_env_vars=False)
        assert list(second.snapshot()["nodes"]) == ["sink"]
        assert first.snapshot()["nodes"]["source"]["returned_count"] == 1


async def test_real_frozen_cache_call_is_timed_without_cache_category():
    from lfx.services.cache.utils import CacheMiss

    target = graph()
    store = {}

    async def get_cache(key):
        return store.get(key, CacheMiss())

    async def set_cache(key, data):
        store[key] = {"result": data}
        return True

    with (
        patch("lfx.services.deps.get_db_service", return_value=NoopDatabaseService()),
        target.collect_execution_metrics() as metrics,
    ):
        await target.build_vertex("source", get_cache=get_cache, set_cache=set_cache)
        target.get_vertex("source").frozen = True
        await target.build_vertex("source", get_cache=get_cache, set_cache=set_cache)
    row = metrics.snapshot()["nodes"]["source"]
    assert row["call_count"] == row["returned_count"] == 2
    assert target.get_vertex("source").result.used_frozen_result is True
    assert "cached_count" not in row


async def test_loader_recipe_owns_recorded_graph():
    from pathlib import Path

    from lfx.load import aload_flow_from_json
    from lfx.schema.schema import InputValueRequest

    source = Path(__file__).parents[2] / "data" / "simple_chat_no_llm.json"
    with patch("lfx.services.deps.get_db_service", return_value=NoopDatabaseService()):
        target = await aload_flow_from_json(source)
        with target.collect_execution_metrics() as metrics:
            results = [r async for r in target.async_start(inputs=InputValueRequest(input_value="recorded loader"))]
    delivered = [r.vertex.built_object["message"].data["text"] for r in results if getattr(r, "vertex", None)]
    assert delivered == ["recorded loader", "recorded loader"]
    assert set(metrics.snapshot()["nodes"]) == {vertex.id for vertex in target.vertices}
    assert all(node["returned_count"] == 1 for node in metrics.snapshot()["nodes"].values())


async def test_clock_faults_leave_returns_and_elapsed_usable(monkeypatch):
    target = graph()
    with target.collect_execution_metrics() as metrics:
        monkeypatch.setattr(module, "_clock", lambda: (_ for _ in ()).throw(RuntimeError("clock fault")))
        assert metrics._begin("source") is None
        assert metrics.snapshot()["elapsed_seconds"] == 0.0
        assert metrics.snapshot()["incomplete"] is True
    assert metrics.snapshot()["elapsed_seconds"] == 0.0
    assert target._execution_metrics is None


@pytest.mark.parametrize("error", [None, RuntimeError("primary"), asyncio.CancelledError(), SystemExit(19)])
async def test_public_foreign_scope_exit_preserves_primary_and_owner_recovery(error):
    target = graph()
    scope = target.collect_execution_metrics()
    metrics = scope.__enter__()

    class EnteredScope:
        def __enter__(self):
            return metrics

        def __exit__(self, *args):
            return scope.__exit__(*args)

    async def foreign():
        if error is None:
            with pytest.raises(RuntimeError, match="scope exit"), EnteredScope():
                pass
        else:
            with pytest.raises(type(error)) as caught, EnteredScope():
                raise error
            assert caught.value is error

    await asyncio.to_thread(lambda: asyncio.run(foreign()))
    assert metrics._active
    assert target._execution_metrics is metrics
    assert scope.__exit__(None, None, None) is False
    assert not metrics._active
    assert target._execution_metrics is None
    frozen = metrics.snapshot()
    assert scope.__exit__(None, None, None) is False
    with target.collect_execution_metrics() as newer:
        assert newer.snapshot()["nodes"] == {}
    assert metrics.snapshot() == frozen


async def test_inner_snapshot_rows_are_detached_and_elapsed_never_decreases(monkeypatch):
    target = graph()
    monkeypatch.setattr(module, "_clock", iter([0.0, 1.0, 2.0, 5.0, 4.0, 6.0]).__next__)
    with target.collect_execution_metrics() as metrics:
        metrics._finish("source", metrics._begin("source"), "returned")
        snapshot = metrics.snapshot()
        assert snapshot["elapsed_seconds"] == 5.0
        snapshot["nodes"]["source"]["call_count"] = 999
        next_snapshot = metrics.snapshot()
        assert next_snapshot["nodes"]["source"]["call_count"] == 1
        assert next_snapshot["elapsed_seconds"] == 5.0
        assert next_snapshot["incomplete"] is True
    assert metrics.snapshot()["elapsed_seconds"] == 6.0


async def test_actual_build_completes_in_new_scope_without_late_mutation(monkeypatch):
    import asyncio

    from lfx.components.input_output import ChatInput

    target = Graph()
    target.add_component(ChatInput(_id="gated").set(input_value="late", should_store_message=False), "gated")
    target.prepare()
    vertex = target.get_vertex("gated")
    original = vertex.build
    entered, release = asyncio.Event(), asyncio.Event()

    async def wait_build(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(vertex, "build", wait_build)
    with target.collect_execution_metrics() as old:
        task = asyncio.create_task(target.build_vertex("gated"))
        await asyncio.wait_for(entered.wait(), 5)
    before = old.snapshot(), old._inflight, old._active, old._incomplete
    assert old._inflight == 1
    assert old.snapshot()["incomplete"] is True
    with target.collect_execution_metrics() as current:
        release.set()
        result = await task
        assert result.vertex.id == "gated"
        assert current.snapshot()["nodes"] == {}
    assert (old.snapshot(), old._inflight, old._active, old._incomplete) == before

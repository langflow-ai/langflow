# ruff: noqa: ARG001, ARG002
"""Dependency-ready eligibility tests use real connected component instances."""

import copy

import pytest
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.schema.message import Message

from tests.unit.graph.graph._dag_components import InheritedNode, branched, connected


@pytest.mark.parametrize("value", [None, 1, 2, 8])
def test_concurrency_values(value):
    from lfx.graph.graph.dag_scheduler import validate_dag_max_concurrency

    assert validate_dag_max_concurrency(value) == value


@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, "2"])
def test_concurrency_invalid(value):
    from lfx.graph.graph.dag_scheduler import validate_dag_max_concurrency

    with pytest.raises(ValueError, match="positive integer or None"):
        validate_dag_max_concurrency(value)


def test_candidate_uses_edge_topology_not_mutable_predecessor_map():
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate, select_dag_candidate

    graph = connected()
    candidate = inspect_dag_candidate(graph)
    assert not isinstance(candidate, str)
    assert candidate.predecessors["target"] == ("source",)
    graph.predecessor_map["target"].clear()
    assert candidate.predecessors["target"] == ("source",)
    # A stale selected frontier must not authorize an inconsistent run.
    graph.vertices_to_run = {"source", "target"}
    assert isinstance(select_dag_candidate(graph, candidate, ["target"]), str)


@pytest.mark.parametrize("eager", [True, False])
def test_payload_capability_uses_actual_concrete_instance(eager):
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate

    graph = Graph.from_payload(
        copy.deepcopy(connected().dump()), instantiate_components=eager, emit_extension_events=False
    )
    candidate = inspect_dag_candidate(graph)
    assert isinstance(candidate, str) is not eager


def test_inherited_capability_does_not_opt_in():
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate

    assert isinstance(inspect_dag_candidate(connected(InheritedNode)), str)


@pytest.mark.parametrize(
    "change",
    [
        lambda g: setattr(g.vertex_map["source"], "built", True),
        lambda g: setattr(g.vertex_map["source"], "is_state", True),
        lambda g: setattr(g.vertex_map["source"], "custom_component", None),
        lambda g: setattr(g, "checkpointing_enabled", True),
        lambda g: setattr(g, "resumed_from_checkpoint", True),
        lambda g: setattr(g, "pause_requested", True),
        lambda g: setattr(g, "pause_probe", lambda _: False),
        lambda g: g.conditionally_excluded_vertices.add("target"),
        lambda g: g.activated_vertices.append("target"),
        lambda g: g.edges.append(g.edges[0]),
        lambda g: g.vertex_map["source"].params.update(stream=True),
    ],
)
def test_unsupported_candidate_falls_back(change):
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate

    graph = connected()
    change(graph)
    assert isinstance(inspect_dag_candidate(graph), str)


def test_selection_is_detached_and_source_ordered():
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate, select_dag_candidate

    graph = connected()
    candidate = inspect_dag_candidate(graph)
    first = graph.sort_vertices()
    selection = select_dag_candidate(graph, candidate, first)
    assert not isinstance(selection, str)
    assert selection.predecessors["target"] == ("source",)
    assert selection.ids == tuple(vertex.id for vertex in graph.vertices)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, -1, True, 1.0, "2"])
async def test_arun_invalid_option_rejected_before_dispatch(value, monkeypatch):
    graph = connected()

    async def unexpected():
        pytest.fail("invalid option reached coordinator")

    monkeypatch.setattr("lfx.execution.aget_default_coordinator", unexpected)
    with pytest.raises(ValueError, match="positive integer or None"):
        await graph.arun(inputs=[{}], dag_max_concurrency=value)


@pytest.mark.asyncio
@pytest.mark.parametrize("execution_fails", [False, True])
async def test_explicit_option_uses_reserved_executor_flag(monkeypatch, execution_fails):
    from unittest.mock import AsyncMock

    from lfx.execution import Coordinator, ExecutorRegistry, get_default_coordinator, set_default_coordinator
    from lfx.execution.executor import Executor
    from lfx.execution.types import RunComplete

    seen = []

    class Recording(Executor):
        kind = "in-process"

        async def execute(self, unit):
            seen.append(unit.runtime_options)
            if execution_fails:
                msg = "controlled executor failure"
                raise RuntimeError(msg)
            yield RunComplete(outputs=[])

    registry = ExecutorRegistry()
    registry.register(Recording())
    prior = get_default_coordinator()
    set_default_coordinator(Coordinator(registry=registry))
    try:
        if execution_fails:
            with pytest.raises(RuntimeError, match="controlled executor failure"):
                await connected().arun(inputs=[{}], dag_max_concurrency=2)
        else:
            await connected().arun(inputs=[{}], dag_max_concurrency=2)
        assert seen[0]["_dag_max_concurrency"] == 2
        assert "dag_max_concurrency" not in seen[0]
    finally:
        set_default_coordinator(prior)
    assert get_default_coordinator() is prior
    restored_run = AsyncMock(return_value=["restored-coordinator"])
    monkeypatch.setattr(prior, "run_to_completion", restored_run)
    assert await Graph().arun(inputs=[{}]) == ["restored-coordinator"]
    restored_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_custom_coordinator_keeps_original_call(monkeypatch):
    class Strict:
        async def run_to_completion(
            self,
            graph,
            *,
            inputs,
            inputs_components,
            types,
            outputs,
            session_id,
            stream,
            fallback_to_env_vars,
            event_manager,
            _use_arun_legacy,
        ):
            return ["strict-result"]

    async def coordinator():
        return Strict()

    monkeypatch.setattr("lfx.execution.aget_default_coordinator", coordinator)
    assert await connected().arun(inputs=[{}], dag_max_concurrency=2) == ["strict-result"]


@pytest.mark.asyncio
async def test_process_invalid_option_rejected_before_sort(monkeypatch):
    graph = connected()

    def unexpected(**kwargs):
        pytest.fail("invalid option reached sort")

    monkeypatch.setattr(graph, "sort_vertices", unexpected)
    with pytest.raises(ValueError, match="positive integer or None"):
        await graph.process(fallback_to_env_vars=False, dag_max_concurrency=False)


def test_base_component_does_not_opt_in():
    assert Component.supports_dependency_ready_scheduling is False


@pytest.mark.asyncio
async def test_in_process_reserved_option_reaches_standard_graph(monkeypatch):
    from lfx.execution import set_default_coordinator

    set_default_coordinator(None)
    graph = connected()
    seen = []

    async def process(**kwargs):
        seen.append(kwargs)
        return graph

    monkeypatch.setattr(graph, "process", process)
    await graph.arun(inputs=[{}], dag_max_concurrency=2)
    assert seen[0]["dag_max_concurrency"] == 2


@pytest.mark.parametrize(
    "change",
    [
        lambda g: setattr(g.vertex_map["source"], "result", {"old": True}),
        lambda g: setattr(g.vertex_map["source"], "frozen", True),
        lambda g: setattr(g.vertex_map["source"], "_is_loop", True),
        lambda g: g.vertex_map["source"].data["node"].update(tool_mode=True),
        lambda g: g.vertex_map["source"]
        .custom_component._outputs_map["message"]
        .__setattr__("value", Message(text="old")),
        lambda g: setattr(g.vertex_map["source"].custom_component, "supports_dependency_ready_scheduling", False),
    ],
)
def test_more_unsupported_state(change):
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate

    graph = connected()
    change(graph)
    # Instance attributes cannot opt out an actual class promise; cached output can.
    if graph.vertex_map["source"].custom_component.__dict__.get("supports_dependency_ready_scheduling") is False:
        assert not isinstance(inspect_dag_candidate(graph), str)
    else:
        assert isinstance(inspect_dag_candidate(graph), str)


def test_instance_capability_cannot_opt_in():
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate

    graph = connected(InheritedNode)
    for vertex in graph.vertices:
        vertex.custom_component.supports_dependency_ready_scheduling = True
        vertex.data["node"]["supports_dependency_ready_scheduling"] = True
    assert isinstance(inspect_dag_candidate(graph), str)


def test_partial_selection_cannot_skip_predecessor():
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate, select_dag_candidate

    graph = connected()
    candidate = inspect_dag_candidate(graph)
    graph.vertices_to_run = {"target"}
    assert isinstance(select_dag_candidate(graph, candidate, ["target"]), str)


def test_duplicate_source_missing_endpoint_and_cycle_fall_back():
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate

    graph = connected()
    edge = graph.edges[0]
    graph.edges.append(copy.copy(edge))
    assert isinstance(inspect_dag_candidate(graph), str)
    graph.edges.pop()
    original = edge.target_id
    edge.target_id = "missing"
    assert isinstance(inspect_dag_candidate(graph), str)
    edge.target_id = edge.source_id
    assert isinstance(inspect_dag_candidate(graph), str)
    edge.target_id = original
    reverse = copy.copy(edge)
    reverse.source_id, reverse.target_id = edge.target_id, edge.source_id
    graph.edges.append(reverse)
    assert isinstance(inspect_dag_candidate(graph), str)


@pytest.mark.asyncio
async def test_fast_successor_starts_before_slow_sibling_finishes(monkeypatch):
    import asyncio

    graph = branched()
    build = graph.build_vertex
    release = asyncio.Event()
    child_started = asyncio.Event()
    active = set()
    peaks = []
    before = {key: list(value) for key, value in graph.predecessor_map.items()}

    async def controlled(vertex_id, **kwargs):
        active.add(vertex_id)
        peaks.append(len(active))
        try:
            if vertex_id == "slow":
                await release.wait()
            if vertex_id == "child":
                child_started.set()
            return await build(vertex_id=vertex_id, **kwargs)
        finally:
            active.remove(vertex_id)

    monkeypatch.setattr(graph, "build_vertex", controlled)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    try:
        await asyncio.wait_for(child_started.wait(), timeout=3)
        assert "slow" in active
    finally:
        release.set()
        await task
    assert max(peaks) <= 2
    assert not active
    assert before == dict(graph.predecessor_map)
    assert graph.run_manager.ran_at_least_once == {"source", "slow", "fast", "child", "merge"}
    assert all(graph.run_manager.run_predecessors[key] is not value for key, value in graph.predecessor_map.items())


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [1, 2, 8])
async def test_every_selected_vertex_executes_once_and_bound_holds(limit, monkeypatch):
    import asyncio
    from collections import Counter

    graph = branched()
    build = graph.build_vertex
    calls = Counter()
    active = 0
    peak = 0

    async def controlled(vertex_id, **kwargs):
        nonlocal active, peak
        calls[vertex_id] += 1
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0)
            return await build(vertex_id=vertex_id, **kwargs)
        finally:
            active -= 1

    monkeypatch.setattr(graph, "build_vertex", controlled)
    await graph.process(fallback_to_env_vars=False, dag_max_concurrency=limit)
    assert calls == dict.fromkeys(["source", "slow", "fast", "child", "merge"], 1)
    assert peak <= limit
    assert active == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["persist", "emit"])
async def test_completion_handling_finishes_before_descendant_admission(phase, monkeypatch):
    import asyncio

    graph = connected()
    graph.flow_id = "flow"
    release = asyncio.Event()
    entered = asyncio.Event()
    build = graph.build_vertex
    builds = []

    async def controlled(vertex_id, **kwargs):
        builds.append(vertex_id)
        return await build(vertex_id=vertex_id, **kwargs)

    async def persist(**kwargs):
        if phase == "persist" and kwargs["vertex_id"] == "source":
            entered.set()
            await release.wait()

    async def emit(**kwargs):
        if phase == "emit" and kwargs["vertex_id"] == "source":
            entered.set()
            await release.wait()

    monkeypatch.setattr(graph, "build_vertex", controlled)
    monkeypatch.setattr("lfx.graph.graph.base.log_vertex_build", persist)
    monkeypatch.setattr("lfx.graph.utils.emit_vertex_build_event", emit)
    task = asyncio.create_task(graph.process(fallback_to_env_vars=False, dag_max_concurrency=2))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        assert builds == ["source"]
    finally:
        release.set()
        await task
    assert builds == ["source", "target"]


@pytest.mark.asyncio
@pytest.mark.parametrize("ephemeral", [True, False])
@pytest.mark.parametrize("flow_id", [None, "flow"])
@pytest.mark.parametrize("limit", [None, 2])
async def test_full_result_payload_gates_preserved_with_named_transport_doubles(ephemeral, flow_id, limit, monkeypatch):
    graph = connected()
    graph.flow_id = flow_id
    graph.persist_messages = not ephemeral
    persisted, emitted, results = [], [], {}
    build = graph.build_vertex

    async def controlled(vertex_id, **kwargs):
        result = await build(vertex_id=vertex_id, **kwargs)
        results[vertex_id] = result
        return result

    async def persist(**kwargs):
        persisted.append(kwargs)

    async def emit(**kwargs):
        emitted.append(kwargs)

    monkeypatch.setattr(graph, "build_vertex", controlled)
    monkeypatch.setattr("lfx.graph.graph.base.log_vertex_build", persist)
    monkeypatch.setattr("lfx.graph.utils.emit_vertex_build_event", emit)
    await graph.process(fallback_to_env_vars=False, dag_max_concurrency=limit)
    assert [item["vertex_id"] for item in persisted] == (["source", "target"] if flow_id and not ephemeral else [])
    assert [item["vertex_id"] for item in emitted] == (["source", "target"] if flow_id else [])
    for item in persisted:
        result = results[item["vertex_id"]]
        assert item == {
            "flow_id": "flow",
            "vertex_id": result.vertex.id,
            "valid": result.valid,
            "params": result.params,
            "data": result.result_dict,
            "artifacts": result.artifacts,
            "job_id": graph._run_id,
        }
    for item in emitted:
        result = results[item["vertex_id"]]
        next_ids = ["target"] if item["vertex_id"] == "source" else []
        assert item == {
            "flow_id": "flow",
            "vertex_id": result.vertex.id,
            "valid": result.valid,
            "params": result.params,
            "data_dict": result.result_dict,
            "artifacts_dict": result.artifacts,
            "next_vertices_ids": next_ids,
            "top_level_vertices": next_ids,
            "inactivated_vertices": [],
        }


@pytest.mark.asyncio
async def test_fallback_sorts_once_and_executes_each_vertex_once(monkeypatch):
    graph = connected(InheritedNode)
    sort, build = graph.sort_vertices, graph.build_vertex
    sorted_calls, built = [], []

    def counted(**kwargs):
        sorted_calls.append(kwargs)
        return sort(**kwargs)

    async def controlled(vertex_id, **kwargs):
        built.append(vertex_id)
        return await build(vertex_id=vertex_id, **kwargs)

    monkeypatch.setattr(graph, "sort_vertices", counted)
    monkeypatch.setattr(graph, "build_vertex", controlled)
    await graph.process(fallback_to_env_vars=False, dag_max_concurrency=2)
    assert len(sorted_calls) == 1
    assert built == ["source", "target"]


@pytest.mark.asyncio
async def test_reused_built_graph_falls_back_instead_of_promising_new_work(monkeypatch):
    from lfx.execution import set_default_coordinator

    set_default_coordinator(None)
    graph = connected()
    await graph.arun(inputs=[{}], outputs=["target"], dag_max_concurrency=2)
    old = graph.vertex_map["target"].custom_component._outputs_map["message"].value
    calls = []
    execute = graph._execute_tasks

    async def counted(*args, **kwargs):
        calls.append(True)
        return await execute(*args, **kwargs)

    monkeypatch.setattr(graph, "_execute_tasks", counted)
    await graph.arun(inputs=[{}], outputs=["target"], dag_max_concurrency=2)
    assert calls
    assert graph.vertex_map["target"].custom_component._outputs_map["message"].value is old


@pytest.mark.asyncio
async def test_ready_ids_can_wait_for_capacity_in_graph_order(monkeypatch):
    graph = branched()
    emitted = []

    async def event(result, next_ids):
        emitted.append((result.vertex.id, next_ids))

    monkeypatch.setattr(graph, "_emit_vertex_build_result", event)
    await graph.process(fallback_to_env_vars=False, dag_max_concurrency=1)
    graph_order = [key for key in (vertex.id for vertex in graph.vertices) if key in {"slow", "fast"}]
    assert emitted[0] == ("source", graph_order)
    positions = {key: i for i, (key, _) in enumerate(emitted)}
    assert positions[graph_order[0]] < positions[graph_order[1]]
    assert emitted[-1] == ("merge", [])


@pytest.mark.asyncio
async def test_same_completion_group_error_uses_graph_order_and_retrieves_all(monkeypatch):
    import asyncio

    graph = branched()
    build = graph.build_vertex
    errors = {key: LookupError(key) for key in ("slow", "fast")}

    async def controlled(vertex_id, **kwargs):
        if vertex_id in errors:
            raise errors[vertex_id]
        return await build(vertex_id=vertex_id, **kwargs)

    # Both immediate failures are in the same FIRST_COMPLETED observed group.
    monkeypatch.setattr(graph, "build_vertex", controlled)
    expected = next(vertex.id for vertex in graph.vertices if vertex.id in errors)
    with pytest.raises(LookupError, match=expected) as caught:
        await graph.process(fallback_to_env_vars=False, dag_max_concurrency=2)
    assert caught.value is errors[expected]
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_disconnected_unsupported_vertex_forces_whole_graph_fallback(monkeypatch):
    graph = connected()
    unsupported = connected(InheritedNode).vertex_map["source"]
    unsupported.id = "unselected"
    graph.vertices.append(unsupported)
    graph.vertex_map["unselected"] = unsupported
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate

    assert isinstance(inspect_dag_candidate(graph), str)


def test_deferred_inspection_does_not_construct(monkeypatch):
    graph = Graph.from_payload(
        copy.deepcopy(connected().dump()), instantiate_components=False, emit_extension_events=False
    )
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate

    def forbidden(*args, **kwargs):
        pytest.fail("inspection constructed components")

    monkeypatch.setattr(graph, "_instantiate_components_in_vertices", forbidden)
    assert isinstance(inspect_dag_candidate(graph), str)
    assert all(vertex.custom_component is None for vertex in graph.vertices)


def test_custom_graph_and_changed_edge_snapshot_rejected():
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate, select_dag_candidate

    class CustomGraph(Graph):
        pass

    assert isinstance(inspect_dag_candidate(CustomGraph()), str)
    graph = connected()
    candidate = inspect_dag_candidate(graph)
    first = graph.sort_vertices()
    graph.edges.clear()
    assert isinstance(select_dag_candidate(graph, candidate, first), str)


def test_unknown_component_and_stale_vertex_map_fall_back():
    from lfx.graph.graph.dag_scheduler import inspect_dag_candidate

    class Unknown:
        supports_dependency_ready_scheduling = True

    graph = connected()
    graph.vertex_map["source"].custom_component = Unknown()
    assert isinstance(inspect_dag_candidate(graph), str)
    graph = connected()
    graph.vertex_map.pop("source")
    assert isinstance(inspect_dag_candidate(graph), str)


@pytest.mark.asyncio
@pytest.mark.parametrize("graph_subclass", [False, True])
@pytest.mark.parametrize("coordinator_kind", ["standard", "subclass", "strict"])
@pytest.mark.parametrize("limit", [None, 2])
async def test_arun_warns_only_when_explicit_bound_is_dropped(graph_subclass, coordinator_kind, limit, monkeypatch):
    from unittest.mock import Mock

    from lfx.execution import Coordinator, ExecutorRegistry

    class CustomGraph(Graph):
        pass

    class CustomCoordinator(Coordinator):
        pass

    class StrictCoordinator:
        async def run_to_completion(
            self,
            graph,
            *,
            inputs,
            inputs_components,
            types,
            outputs,
            session_id,
            stream,
            fallback_to_env_vars,
            event_manager,
            _use_arun_legacy,
        ):
            seen.append({"inputs": inputs, "_use_arun_legacy": _use_arun_legacy})
            return ["fallback-result"]

    graph = CustomGraph() if graph_subclass else Graph()
    coordinator_class = {"standard": Coordinator, "subclass": CustomCoordinator, "strict": StrictCoordinator}[
        coordinator_kind
    ]
    coordinator = (
        coordinator_class() if coordinator_kind == "strict" else coordinator_class(registry=ExecutorRegistry())
    )
    seen = []
    supported = not graph_subclass and coordinator_kind == "standard"
    if supported:

        async def record(graph, **kwargs):
            seen.append(kwargs)
            return ["standard-result"]

        monkeypatch.setattr(coordinator, "run_to_completion", record)
    elif coordinator_kind != "strict":
        monkeypatch.setattr(coordinator, "run_to_completion", StrictCoordinator().run_to_completion)

    async def get_coordinator():
        return coordinator

    warning = Mock()
    monkeypatch.setattr("lfx.execution.aget_default_coordinator", get_coordinator)
    monkeypatch.setattr("lfx.graph.graph.base.logger.warning", warning)
    result = await graph.arun(inputs=[{"secret": "never-log-this"}], dag_max_concurrency=limit)
    assert result == (["standard-result"] if supported else ["fallback-result"])
    assert len(seen) == 1
    assert seen[0]["inputs"] == [{"secret": "never-log-this"}]
    assert seen[0]["_use_arun_legacy"] is True
    if supported and limit is not None:
        assert seen[0]["_dag_max_concurrency"] == limit
    else:
        assert "_dag_max_concurrency" not in seen[0]
    if limit is None or supported:
        warning.assert_not_called()
    else:
        warning.assert_called_once()
        template, *args = warning.call_args.args
        text = template % tuple(args)
        assert "dag_max_concurrency=2" in text
        assert "ignored" in text
        assert "falling back" in text
        assert f"Graph type: {type(graph).__name__}" in text
        assert f"coordinator type: {type(coordinator).__name__}" in text
        assert "never-log-this" not in text
        assert "secret" not in text


@pytest.mark.asyncio
async def test_invalid_arun_bound_does_not_log_fallback(monkeypatch):
    from unittest.mock import Mock

    warning = Mock()
    monkeypatch.setattr("lfx.graph.graph.base.logger.warning", warning)
    with pytest.raises(ValueError, match="positive integer or None"):
        await Graph().arun(inputs=[{}], dag_max_concurrency=0)
    warning.assert_not_called()


@pytest.mark.parametrize("log_env", ["development", "container_json"])
def test_arun_fallback_warning_uses_real_production_logger(log_env):
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(
        """
        import asyncio
        import io
        import json
        import sys
        from lfx.execution import Coordinator, ExecutorRegistry
        from lfx.graph import Graph
        from lfx.log.logger import configure
        import lfx.execution

        class SubGraph(Graph):
            pass

        class SubCoordinator(Coordinator):
            pass

        class StrictCoordinator:
            async def run_to_completion(self, graph, *, inputs, inputs_components,
                types, outputs, session_id, stream, fallback_to_env_vars,
                event_manager, _use_arun_legacy):
                return ["completed"]

        async def complete(graph, **kwargs):
            assert "_dag_max_concurrency" not in kwargs
            return ["completed"]

        output = io.StringIO()
        configure(log_level="WARNING", log_env=sys.argv[1], output_file=output)

        async def run():
            for kind in ("graph", "coordinator-subclass", "strict"):
                graph = SubGraph() if kind == "graph" else Graph()
                if kind == "strict":
                    coordinator = StrictCoordinator()
                else:
                    cls = Coordinator if kind == "graph" else SubCoordinator
                    coordinator = cls(registry=ExecutorRegistry())
                    coordinator.run_to_completion = complete
                async def get_coordinator():
                    return coordinator
                lfx.execution.aget_default_coordinator = get_coordinator
                assert await graph.arun(inputs=[{"private": "never-log-this"}],
                    dag_max_concurrency=3) == ["completed"]
        asyncio.run(run())
        text = output.getvalue()
        assert text.count("dag_max_concurrency=3") == 3, text
        assert "falling back" in text, text
        assert "never-log-this" not in text and "private" not in text, text
        if sys.argv[1] == "container_json":
            events = [json.loads(line) for line in text.splitlines()]
            assert len(events) == 3, events
            assert all(event["level"] == "warning" for event in events), events
        print("REAL_LOGGER_OK")
        """
    )
    result = subprocess.run(  # noqa: S603 - fixed local script and parametrized log modes, no shell
        [sys.executable, "-c", script, log_env], capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "REAL_LOGGER_OK" in result.stdout


@pytest.mark.parametrize("log_env", ["development", "container_json"])
def test_secondary_finalization_logging_preserves_primary_with_real_logger(log_env):
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(
        """
        import asyncio
        import io
        import json
        import sys
        from lfx.graph import Graph
        from lfx.graph.graph.dag_scheduler import DagRunContext, finalize_dag_run
        from lfx.log.logger import configure

        output = io.StringIO()
        configure(log_level="DEBUG", log_env=sys.argv[1], output_file=output)
        async def run():
            graph = Graph()
            primary = LookupError("private-primary-message")
            async def end(error=None):
                assert error is primary
                raise RuntimeError("private-secondary-message")
            graph.end_all_traces = end
            context = DagRunContext(eligible=True, initialization_attempted=True, primary=primary)
            await finalize_dag_run(graph, context)
            assert context.primary is primary
            assert context.finalized
        asyncio.run(run())
        text = output.getvalue()
        assert "Secondary DAG finalization failure: RuntimeError" in text, text
        assert "private-primary-message" not in text, text
        assert "private-secondary-message" not in text, text
        if sys.argv[1] == "container_json":
            events = [json.loads(line) for line in text.splitlines()]
            assert any(event["level"] == "debug" and
                event["event"] == "Secondary DAG finalization failure: RuntimeError" for event in events), events
        print("PRIMARY_PRESERVED")
        """
    )
    result = subprocess.run(  # noqa: S603 - fixed local script and parametrized log modes, no shell
        [sys.executable, "-c", script, log_env], capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PRIMARY_PRESERVED" in result.stdout

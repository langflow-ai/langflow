"""Automatic diagnostic history is independent of scheduler call order."""

import copy
from enum import IntEnum
from unittest.mock import patch

import pytest
from lfx.graph.graph.base import Graph


class IntPolicy(IntEnum):
    ONE = 1


@pytest.mark.parametrize("limit", [None, 0, 1, 3])
def test_history_retains_suffix_and_list_identity(limit):
    graph = Graph(snapshot_history_limit=limit)
    alias = graph._snapshots
    with patch.object(graph, "get_snapshot", side_effect=[{"step": i} for i in range(6)]):
        for i in range(6):
            graph._record_snapshot(str(i))
    expected = list(range(6)) if limit is None else list(range(6))[-limit:] if limit else []
    assert alias is graph._snapshots
    assert alias == [{"step": i} for i in expected]
    assert graph._call_order == [str(i) for i in range(6)]


@pytest.mark.parametrize("limit", [-1, True, False, 1.5, "1", IntPolicy.ONE])
def test_invalid_policy_precedes_context_and_payload_errors(limit):
    error = ValueError if type(limit) is int else TypeError
    with pytest.raises(error):
        Graph(context=object(), snapshot_history_limit=limit)
    with pytest.raises(error):
        Graph.from_payload(None, snapshot_history_limit=limit)


def test_disabled_no_automatic_copy_but_explicit_snapshot_is_detached():
    graph = Graph(snapshot_history_limit=0)
    with patch.object(graph, "get_snapshot", side_effect=AssertionError("automatic copy")):
        graph._record_snapshot("vertex")
        graph._record_snapshot("")
        graph._record_snapshot(None)
    assert graph._call_order == ["vertex"]
    assert graph._snapshots == []
    snapshot = graph.get_snapshot()
    assert set(snapshot) == {
        "run_manager",
        "run_queue",
        "vertices_layers",
        "first_layer",
        "inactive_vertices",
        "activated_vertices",
    }
    graph.vertices_layers.append(["changed"])
    assert snapshot["vertices_layers"] == []


def test_enabled_snapshot_error_does_not_append_call_order():
    graph = Graph()
    with (
        patch.object(graph, "get_snapshot", side_effect=RuntimeError("snapshot")),
        pytest.raises(RuntimeError, match="snapshot"),
    ):
        graph._record_snapshot("vertex")
    assert graph._call_order == []


@pytest.mark.parametrize("limit", [None, 0, 3])
def test_state_roundtrip_actual_policy_and_old_missing_lists(limit):
    graph = Graph(snapshot_history_limit=limit)
    state = graph.__getstate__()
    assert state["_snapshot_history_limit"] == limit
    assert "_snapshots" not in state
    assert "_call_order" not in state
    restored = Graph.__new__(Graph)
    restored.__setstate__(state)
    assert restored.__dict__["_snapshot_history_limit"] == limit
    with patch.object(restored, "get_snapshot", return_value={"controlled": True}):
        restored._record_snapshot("vertex")
    assert len(restored._snapshots) == (0 if limit == 0 else 1)
    assert restored._call_order == ["vertex"]
    old_state = graph.__getstate__()
    old_state.pop("_snapshot_history_limit")
    restored.__setstate__(old_state)
    assert restored.snapshot_history_limit is None
    assert restored._call_order == ["vertex"]


def test_state_preserves_incoming_or_existing_list_identity():
    graph = Graph()
    old_history, old_order = graph._snapshots, graph._call_order
    graph.__setstate__(graph.__getstate__())
    assert graph._snapshots is old_history
    assert graph._call_order is old_order
    state = graph.__getstate__()
    history, order = [{"incoming": True}], ["incoming"]
    state.update(_snapshots=history, _call_order=order)
    graph.__setstate__(state)
    assert graph._snapshots is history
    assert graph._call_order is order


@pytest.mark.parametrize("limit", [None, 0, 1, 3])
def test_empty_graph_copies_and_addition_preserve_left_policy(limit):
    graph = Graph(snapshot_history_limit=limit)
    assert copy.deepcopy(graph).snapshot_history_limit == limit
    assert (graph + Graph()).snapshot_history_limit == limit
    graph += Graph()
    assert graph.snapshot_history_limit == limit
    with pytest.raises(AttributeError):
        graph.snapshot_history_limit = 2


@pytest.mark.parametrize("limit", [-1, True, "1"])
def test_invalid_stored_policy_fails_before_updating_object(limit):
    graph = Graph()
    state = graph.__getstate__()
    state["_snapshot_history_limit"] = limit
    error = ValueError if type(limit) is int else TypeError
    with pytest.raises(error):
        graph.__setstate__(state)
    assert graph.snapshot_history_limit is None


@pytest.mark.parametrize("limit", [None, 0, 3])
def test_pickle_roundtrip_preserves_backing_policy(limit):
    import pickle

    restored = pickle.loads(pickle.dumps(Graph(snapshot_history_limit=limit)))  # noqa: S301
    assert restored.__dict__["_snapshot_history_limit"] == limit
    assert restored._snapshots == []
    assert restored._call_order == []


class OldSignatureGraph(Graph):
    def __init__(
        self,
        *,
        flow_id=None,
        flow_name=None,
        user_id=None,
        context=None,
        instantiate_components=True,
        authorized_legacy_flow_ids=None,
        description=None,
    ):
        super().__init__(
            flow_id=flow_id,
            flow_name=flow_name,
            user_id=user_id,
            context=context,
            instantiate_components=instantiate_components,
            authorized_legacy_flow_ids=authorized_legacy_flow_ids,
            description=description,
        )


class SwallowingGraph(Graph):
    def __init__(self, **kwargs):
        kwargs.pop("snapshot_history_limit", None)
        super().__init__(**kwargs)


def test_old_signature_default_copy_and_swallowing_nondefault_rejection():
    assert copy.deepcopy(OldSignatureGraph()).snapshot_history_limit is None
    graph = SwallowingGraph()
    graph._snapshot_history_limit = 0
    with pytest.raises(TypeError, match="did not preserve"):
        copy.deepcopy(graph)
    with pytest.raises(TypeError, match="did not preserve"):
        Graph._verify_snapshot_history_policy(object(), 0)


async def test_subgraph_policy_before_prepare():
    graph = Graph(snapshot_history_limit=0)
    async with graph.create_subgraph(set()) as child:
        assert type(child) is Graph
        assert child.snapshot_history_limit == 0
        with patch.object(child, "get_snapshot", side_effect=AssertionError("copy")):
            child._record_snapshot()


async def test_repeated_real_connected_runs_all_policies():
    from lfx.custom import Component
    from lfx.io import MessageInput, Output
    from lfx.schema.message import Message

    class Pass(Component):
        inputs = [MessageInput(name="value")]
        outputs = [Output(name="message", method="run")]

        def run(self) -> Message:
            return self.value or Message(text="echo")

    observed = []
    for limit in [None, 0, 1, 3]:
        nodes = [Pass(_id=f"p{i}") for i in range(4)]
        for i in range(1, 4):
            nodes[i].set(value=nodes[i - 1].run)
        if limit == 0:
            with patch.object(Graph, "get_snapshot", side_effect=AssertionError("constructor copy")):
                graph = Graph(nodes[0], nodes[-1], snapshot_history_limit=limit)
        else:
            graph = Graph(nodes[0], nodes[-1], snapshot_history_limit=limit)
        graph.persist_messages = False
        records = []
        for _ in range(2):
            results = [result async for result in graph.async_start()]
            records.append(
                (
                    len(results),
                    graph.vertices[-1].built_object["message"].text,
                    list(graph._call_order),
                    graph.get_snapshot(),
                )
            )
            if limit is not None:
                assert len(graph._snapshots) <= limit
            if limit == 1:
                prior = graph._snapshots[0]
                graph.prepare()
                assert len(graph._snapshots) == 1
                assert graph._snapshots[0] is not prior
        observed.append(records)
    assert observed[0] == observed[1] == observed[2] == observed[3]


class IntegerSubclass(int):
    pass


def test_custom_integer_subclass_rejected():
    with pytest.raises(TypeError, match="built-in int"):
        Graph(snapshot_history_limit=IntegerSubclass(1))


def test_from_payload_policy_and_default_subclass_compatibility():
    for limit in [None, 0, 1]:
        graph = Graph.from_payload({"nodes": [], "edges": []}, snapshot_history_limit=limit)
        assert graph.snapshot_history_limit == limit
    assert OldSignatureGraph.from_payload({"nodes": [], "edges": []}).snapshot_history_limit is None
    with pytest.raises(TypeError, match="did not preserve"):
        SwallowingGraph.from_payload({"nodes": [], "edges": []}, snapshot_history_limit=0)


@pytest.mark.parametrize("limit", [0, 1])
async def test_loop_iteration_helper_inherits_policy(limit):
    from unittest.mock import AsyncMock

    from lfx.base.flow_controls.loop_utils import execute_loop_body
    from lfx.components.input_output import ChatInput, ChatOutput
    from lfx.schema.data import Data

    start = ChatInput(_id="loop_input", input_value="loop")
    start.set(should_store_message=False)
    end = ChatOutput(_id="loop_output")
    end.set(input_value=start.message_response, should_store_message=False)
    graph = Graph(start, end, snapshot_history_limit=limit)
    children = []

    class Coordinator:
        async def stream(self, child, **_kwargs):
            children.append(child)
            async for result in child.async_start():
                yield result

    with patch("lfx.base.flow_controls.loop_utils.aget_default_coordinator", new=AsyncMock(return_value=Coordinator())):
        outputs = await execute_loop_body(
            graph,
            [Data(data={"value": 1}), Data(data={"value": 2})],
            {"loop_input", "loop_output"},
            None,
            None,
            "loop_output",
        )
    assert len(outputs) == len(children) == 2
    assert children[0] is not children[1]
    assert all(child.snapshot_history_limit == limit for child in children)
    assert all(len(child._snapshots) <= limit for child in children)


@pytest.mark.parametrize("mode", ["success", "failure", "cancel"])
async def test_diamond_events_and_failure_boundaries_match_full_policy(mode):
    import asyncio
    import json

    from lfx.custom import Component
    from lfx.events.event_manager import create_default_event_manager
    from lfx.io import MessageTextInput, Output
    from lfx.schema.message import Message

    class Node(Component):
        inputs = [MessageTextInput(name="value")]
        outputs = [Output(name="message", method="run")]

        async def run(self) -> Message:
            if self._id == "join" and mode == "failure":
                msg = "controlled history failure"
                raise RuntimeError(msg)
            if self._id == "join" and mode == "cancel":
                raise asyncio.CancelledError
            return Message(text=str(self.value or "seed"))

    def normalize(value):
        if isinstance(value, str) and value.startswith("{"):
            try:
                return normalize(json.loads(value))
            except ValueError:
                pass
        if isinstance(value, dict):
            # These event metadata fields are generated independently for each run.
            volatile = {
                "id",
                "timestamp",
                "duration",
                "run_id",
                "session_id",
                "elapsed_time",
                "start_time",
                "end_time",
                "build_time",
                "time",
                "execution_time",
            }
            return {key: normalize(item) for key, item in value.items() if key not in volatile}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    outcomes = []
    for limit in [None, 0, 1, 3]:
        graph = Graph(snapshot_history_limit=limit)
        for name in ["source", "left", "right", "join"]:
            graph.add_component(Node(_id=name), name)
        for source, target in [("source", "left"), ("source", "right"), ("left", "join"), ("right", "join")]:
            graph.add_component_edge(source, ("message", "value"), target)
        graph.persist_messages = False
        queue = asyncio.Queue()
        manager = create_default_event_manager(queue)
        error = None
        results = []
        try:
            async for result in graph.async_start(event_manager=manager):
                results.append(result.vertex.id if hasattr(result, "vertex") else type(result).__name__)  # noqa: PERF401
        except (Exception, asyncio.CancelledError) as exc:
            error = type(exc).__name__
        events = []
        while not queue.empty():
            _, data, _ = queue.get_nowait()
            events.append(normalize(json.loads(data)))
        outcomes.append((error, results, list(graph._call_order), events, graph.get_snapshot()))
        if limit is not None:
            assert len(graph._snapshots) <= limit
    assert outcomes[0] == outcomes[1] == outcomes[2] == outcomes[3]
    if mode == "success":
        assert outcomes[0][0] is None
    else:
        assert outcomes[0][0] is not None
        assert "join" not in outcomes[0][2]


async def test_conditional_branch_policy_parity():
    from lfx.components.input_output import ChatInput, ChatOutput
    from lfx.components.logic.conditional_router import ConditionalRouterComponent

    outcomes = []
    for limit in [None, 0, 1, 3]:
        source = ChatInput(_id="source", input_value="hello")
        source.set(should_store_message=False)
        router = ConditionalRouterComponent(_id="router")
        router.set(input_text=source.message_response, match_text="hello", operator="equals")
        chosen = ChatOutput(_id="chosen")
        chosen.set(input_value=router.true_response, should_store_message=False)
        excluded = ChatOutput(_id="excluded")
        excluded.set(input_value=router.false_response, should_store_message=False)
        graph = Graph(snapshot_history_limit=limit)
        for name, component in [("source", source), ("router", router), ("chosen", chosen), ("excluded", excluded)]:
            graph.add_component(component, name)
        graph.add_component_edge("source", ("message", "input_text"), "router")
        graph.add_component_edge("router", ("true_result", "input_value"), "chosen")
        graph.add_component_edge("router", ("false_result", "input_value"), "excluded")
        graph.persist_messages = False
        results = [result async for result in graph.async_start()]
        outcomes.append(
            (
                len(results),
                list(graph._call_order),
                graph.get_snapshot(),
                graph.get_vertex("chosen").results["message"].text,
            )
        )
        if limit is not None:
            assert len(graph._snapshots) <= limit
    assert outcomes[0] == outcomes[1] == outcomes[2] == outcomes[3]


@pytest.mark.parametrize("arguments", [["--policy", "0"], ["--policy", "1"], ["--policy", "16"], ["--bounded-only"]])
async def test_benchmark_rejects_conflicting_baseline_before_measurement(monkeypatch, arguments):
    import importlib.util
    import sys
    from pathlib import Path
    from unittest.mock import AsyncMock

    script = Path(__file__).resolve().parents[6] / "scripts/benchmark/snapshot_history.py"
    spec = importlib.util.spec_from_file_location("snapshot_benchmark_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sample = AsyncMock(side_effect=AssertionError("measurement must not start"))
    monkeypatch.setattr(module, "sample", sample)
    monkeypatch.setattr(sys, "argv", [str(script), "--size", "2", "--baseline", *arguments])
    with pytest.raises(SystemExit) as error:
        await module.main()
    assert error.value.code == 2
    sample.assert_not_called()

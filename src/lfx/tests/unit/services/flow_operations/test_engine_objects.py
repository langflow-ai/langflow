"""The engine objects' state semantics, the same for the Python engine and the Rust engine.

Staging: a staged batch returns what ``apply`` returns, readers see the
committed graph until ``keep``, ``drop`` leaves the graph as it was, and no
other batch can start while one is staged. Ownership: a result shares nothing
with the engine, and the engine shares nothing with its arguments.
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any

import pytest
from lfx.services.flow_operations.engine import ENGINE_ENV, PythonEngine, RustEngine, get_engine
from lfx.services.flow_operations.exceptions import (
    FlowDataValidationError,
    FlowOperationError,
    FlowOperationValidationError,
)

FIXTURES = Path(__file__).resolve().parents[5] / "lfx-native" / "fixtures"
APPLY_CASES = json.loads((FIXTURES / "apply_cases.json").read_text(encoding="utf-8"))["cases"]


def _has_rust() -> bool:
    try:
        import lfx_native  # noqa: F401
    except ImportError:
        return False
    return True


ENGINES = [
    pytest.param(PythonEngine, id="python"),
    pytest.param(RustEngine, id="rust", marks=pytest.mark.skipif(not _has_rust(), reason="lfx_native is not built")),
]

FLOW = {
    "nodes": [{"id": "a", "data": {"node": {"template": {"t": {"value": "x", "type": "str"}}}}}],
    "edges": [],
    "viewport": {"x": 0, "y": 0, "zoom": 1},
}


def set_value(value: object) -> list[dict[str, Any]]:
    path = ["data", "node", "template", "t", "value"]
    return [{"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": path, "value": value}]}]


def value_of(graph: dict[str, Any]) -> object:
    return graph["nodes"][0]["data"]["node"]["template"]["t"]["value"]


@pytest.fixture(params=ENGINES)
def engine(request):
    return request.param


def test_a_staged_batch_is_read_only_after_keep(engine):
    state = engine.GraphState(FLOW)
    staged = state.stage(set_value("y"), forward=True, backward=True)
    assert staged == engine.GraphState(FLOW).apply(set_value("y"), forward=True, backward=True)
    assert state.staged
    # Readers see the committed graph while the batch waits.
    assert state.to_dict() == FLOW
    assert json.loads(state.to_json()) == FLOW
    state.keep()
    assert not state.staged
    assert value_of(state.to_dict()) == "y"
    assert value_of(json.loads(state.to_json())) == "y"


def test_a_dropped_batch_leaves_the_graph_as_it_was(engine):
    state = engine.GraphState(FLOW)
    state.stage(set_value("y"))
    assert state.drop() is True
    assert not state.staged
    assert state.to_dict() == FLOW
    assert state.drop() is False
    state.apply(set_value("z"))
    assert value_of(state.to_dict()) == "z"


def test_a_staged_batch_refuses_the_next_batch(engine):
    state = engine.GraphState(FLOW)
    state.stage(set_value("y"))
    for call in (
        lambda: state.apply(set_value("z")),
        lambda: state.replay(set_value("z")),
        lambda: state.stage(set_value("z")),
        # Refused before the operations are read, as in the Rust binding.
        lambda: state.apply([{"type": "unknown"}]),
    ):
        with pytest.raises(RuntimeError, match="a batch is staged"):
            call()
    state.keep()
    assert value_of(state.to_dict()) == "y"


def test_a_refused_batch_is_not_staged(engine):
    state = engine.GraphState(FLOW)
    with pytest.raises(FlowOperationValidationError) as refused:
        state.stage([*set_value("y"), {"type": "delete_nodes", "ids": ["missing"]}])
    assert (refused.value.kind, refused.value.code) == ("FlowOperationValidationError", "FLOW_OPERATION_INVALID")
    assert not state.staged
    with pytest.raises(RuntimeError, match="no batch is staged"):
        state.keep()
    assert state.to_dict() == FLOW


def _ignoring_order(flow: dict[str, Any]) -> dict[str, Any]:
    flow = copy.deepcopy(flow)
    for key in ("nodes", "edges"):
        flow[key] = sorted(flow[key], key=lambda entry: entry["id"])
    return flow


@pytest.mark.parametrize("case", [pytest.param(case, id=case["name"]) for case in APPLY_CASES])
def test_stage_keep_and_stage_drop_give_what_apply_gives(engine, case):
    base = case["base"]
    try:
        applied_state = engine.GraphState(base)
    except FlowOperationError:
        return
    try:
        applied = applied_state.apply(case["operations"], forward=True, backward=True)
    except FlowOperationError as error:
        applied = {"error": (error.kind, error.code)}
    for ending in ("keep", "drop"):
        state = engine.GraphState(base)
        try:
            staged = state.stage(case["operations"], forward=True, backward=True)
        except FlowOperationError as error:
            staged = {"error": (error.kind, error.code)}
        assert staged == applied
        assert state.to_dict() == engine.GraphState(base).to_dict()
        if "error" in staged:
            assert not state.staged
            continue
        if ending == "keep":
            state.keep()
            assert engine.graphs_equal(state.to_dict(), applied_state.to_dict())
        else:
            assert state.drop()
            assert _ignoring_order(state.to_dict()) == _ignoring_order(engine.GraphState(base).to_dict())


def test_results_share_nothing_with_the_state(engine):
    state = engine.GraphState(FLOW)
    applied = state.apply(set_value({"deep": ["v"]}), forward=True, backward=True)
    applied["forward_operations"][0]["updates"][0]["value"]["deep"].append("changed")
    graph = state.to_dict()
    graph["nodes"][0]["data"]["node"]["template"]["t"]["value"]["deep"].append("changed")
    assert value_of(state.to_dict()) == {"deep": ["v"]}
    assert value_of(json.loads(state.to_json())) == {"deep": ["v"]}


def test_the_state_shares_nothing_with_its_argument(engine):
    flow = copy.deepcopy(FLOW)
    state = engine.GraphState(flow)
    flow["nodes"][0]["data"]["node"]["template"]["t"]["value"] = "changed by the caller"
    assert value_of(state.to_dict()) == "x"


def test_a_plain_graph_runs_a_save_on_both_engines(engine):
    target = copy.deepcopy(FLOW)
    target["nodes"][0]["data"]["node"]["template"]["t"]["value"] = "y"
    base_plain, target_plain = engine.GraphPlain(FLOW), engine.GraphPlain(target)
    assert target_plain.validate(base_plain) == []
    repaired, fixes = target_plain.repair(base_plain)
    assert fixes == []
    operations = base_plain.ops_diff(repaired)
    assert operations == [{"type": "update_nodes", "updates": set_value("y")[0]["updates"]}]
    assert repaired.graph_hash() == engine.graph_hash(target)
    assert not base_plain.equals(target_plain)


def test_both_engines_raise_one_error_type_with_the_same_details(engine):
    with pytest.raises(FlowDataValidationError) as refused:
        engine.GraphState({"nodes": [{"id": "a"}], "edges": []})
    assert refused.value.kind == "FlowDataValidationError"
    assert refused.value.code == "FLOW_GRAPH_INVALID"
    assert [violation["code"] for violation in refused.value.details["violations"]] == ["NODE_DATA_NOT_OBJECT"]
    assert [violation.code.value for violation in refused.value.violations] == ["NODE_DATA_NOT_OBJECT"]


def test_the_environment_variable_picks_the_engine(monkeypatch):
    monkeypatch.setenv(ENGINE_ENV, "python")
    assert get_engine() is PythonEngine
    monkeypatch.delenv(ENGINE_ENV)
    assert get_engine() is PythonEngine
    monkeypatch.setenv(ENGINE_ENV, "cobol")
    with pytest.raises(ValueError, match=ENGINE_ENV):
        get_engine()
    if _has_rust():
        monkeypatch.setenv(ENGINE_ENV, "rust")
        assert get_engine() is RustEngine


def test_an_item_deleted_and_written_again_in_one_batch_keeps_its_place(engine):
    """A list without positions keeps its array order: the item stays where it was, as one write."""
    node = {"id": "n", "data": {"node": {"template": {}, "outputs": [{"name": "a"}, {"name": "b"}, {"name": "c"}]}}}
    path = ["data", "node", "outputs", {"key": "a"}]
    batch = [
        {"type": "update_nodes", "updates": [{"id": "n", "op": "delete_field", "path": path}]},
        {"type": "update_nodes", "updates": [{"id": "n", "op": "set_field", "path": path, "value": {"name": "a"}}]},
    ]
    state = engine.GraphState({"nodes": [node], "edges": []})
    state.replay(batch)
    outputs = state.to_dict()["nodes"][0]["data"]["node"]["outputs"]
    assert [output["name"] for output in outputs] == ["a", "b", "c"]


NOT_FINITE_FLOW = b'{"nodes": [], "edges": [], "zoom": 1e400}'


@pytest.mark.parametrize(
    "load",
    [
        pytest.param(lambda engine: engine.GraphState(NOT_FINITE_FLOW), id="GraphState"),
        pytest.param(lambda engine: engine.GraphPlain(NOT_FINITE_FLOW), id="GraphPlain"),
        pytest.param(lambda engine: engine.apply(NOT_FINITE_FLOW, []), id="apply"),
        pytest.param(lambda engine: engine.replay(NOT_FINITE_FLOW, []), id="replay"),
    ],
)
def test_a_held_graph_refuses_text_with_a_number_too_large_for_a_double(engine, load):
    """As a ``float`` that is not finite is refused: the engine never holds a number it cannot write."""
    with pytest.raises(FlowDataValidationError) as refused:
        load(engine)
    assert refused.value.code == "FLOW_GRAPH_INVALID"
    assert str(refused.value) == "flow data is not valid JSON: NaN and Infinity are not JSON numbers"


def test_operations_refuse_text_with_a_number_too_large_for_a_double(engine):
    operations = json.dumps(set_value(0)).replace("0}", "-1e400}").encode()
    state = engine.GraphState(FLOW)
    with pytest.raises(FlowOperationValidationError) as refused:
        state.apply(operations)
    assert str(refused.value) == "operations are not valid JSON: NaN and Infinity are not JSON numbers"
    assert value_of(state.to_dict()) == "x"


def test_validation_and_repair_read_a_number_too_large_for_a_double(engine):
    assert [violation["code"] for violation in engine.validate(NOT_FINITE_FLOW)] == ["NON_FINITE_NUMBER"]
    assert engine.repair(NOT_FINITE_FLOW)["flow_data"]["zoom"] is None
    # An integer too large for a double keeps its digits, as a Python int does.
    digits = "1" + "0" * 309
    state = engine.GraphState(b'{"nodes": [], "edges": [], "zoom": ' + digits.encode() + b"}")
    assert state.to_dict()["zoom"] == int(digits)


@pytest.mark.skipif(not _has_rust(), reason="lfx_native is not built")
def test_both_engines_write_the_same_json_text():
    """ASCII only, with the same escapes, numbers and order, from a GraphState and from a GraphPlain."""
    template = {"t": {"value": "é œ 😀 \x7f \\x41 \\U0001f600 \u2028 \x00", "type": "str"}}
    nodes = [
        {"id": f"n{index}", "data": {"node": {"template": template}}, "position": {"x": 1e-7, "y": -0.0}}
        for index in range(4)
    ]
    flow = {"nodes": nodes, "edges": [], "big": 2**70, "zoom": 1.5e300, "ключ": "значение"}
    texts = set()
    for engine in (PythonEngine, RustEngine):
        state = engine.GraphState(flow)
        state.apply([{"type": "delete_nodes", "ids": ["n1"]}])
        texts.update({state.to_json(), engine.GraphPlain(state.to_dict()).to_json()})
    [text] = texts
    assert text.isascii()
    assert [node["id"] for node in json.loads(text)["nodes"]] == ["n0", "n2", "n3"]
    assert json.loads(text) == {**flow, "nodes": [nodes[0], nodes[2], nodes[3]]}


@pytest.mark.parametrize("validate_first", [False, True], ids=["repair", "validate-then-repair"])
def test_a_plain_graph_repairs_the_same_after_a_validate(engine, validate_first):
    """Repair reuses the violations of a validate against the same base, and gives what it gives without them."""
    flow = copy.deepcopy(FLOW)
    flow["zoom"] = 10**400
    flow["nodes"].append({"id": "a", "data": {"node": {"template": {}}}})
    plain, base = engine.GraphPlain(flow), engine.GraphPlain(FLOW)
    if validate_first:
        codes = [violation["code"] for violation in plain.validate(base)]
        assert codes == ["NODE_ID_DUPLICATE", "NON_FINITE_NUMBER"]
    repaired, fixes = plain.repair(base)
    assert [fix["code"] for fix in fixes] == ["NON_FINITE_NUMBER", "NODE_ID_DUPLICATE"]
    assert repaired.to_dict()["zoom"] is None
    assert repaired.validate(base) == []


def test_the_staged_graph_is_the_graph_keep_makes(engine):
    """A server writes the staged graph before its commit, and keeps the batch after."""
    state = engine.GraphState(FLOW)
    with pytest.raises(RuntimeError, match="no batch is staged"):
        state.to_json(staged=True)
    state.stage(set_value("y"))
    staged = state.to_json(staged=True)
    assert value_of(json.loads(staged)) == "y"
    assert value_of(json.loads(state.to_json())) == "x"
    assert value_of(state.to_dict()) == "x"
    state.keep()
    assert state.to_json() == staged
    state.stage([{"type": "delete_nodes", "ids": ["a"]}])
    assert json.loads(state.to_json(staged=True))["nodes"] == []
    assert state.drop()
    with pytest.raises(RuntimeError, match="no batch is staged"):
        state.to_json(staged=True)
    assert state.to_json() == staged


def test_a_state_hashes_as_its_text_does(engine):
    """``GraphState.graph_hash`` is ``GraphPlain.graph_hash`` of the state's JSON text, committed or staged."""
    state = engine.GraphState(FLOW)
    assert state.graph_hash() == engine.GraphPlain(state.to_json().encode()).graph_hash()
    with pytest.raises(RuntimeError, match="no batch is staged"):
        state.graph_hash(staged=True)
    state.stage(set_value("y"))
    staged = state.graph_hash(staged=True)
    assert staged == engine.GraphPlain(state.to_json(staged=True).encode()).graph_hash()
    assert staged != state.graph_hash()
    state.keep()
    assert state.graph_hash() == staged


def test_a_snapshot_keeps_the_graph_as_it_was(engine):
    """A snapshot writes and hashes the committed graph as it was, whatever batches come after."""
    state = engine.GraphState(FLOW)
    text, hashed = state.to_json(), state.graph_hash()
    snapshot = state.snapshot()
    state.apply(set_value("y"))
    state.stage(set_value("z"))
    assert (snapshot.to_json(), snapshot.graph_hash()) == (text, hashed)
    later = state.snapshot()
    assert (later.to_json(), later.graph_hash()) == (state.to_json(), state.graph_hash())
    assert value_of(json.loads(later.to_json())) == "y"


def test_a_snapshot_is_read_on_another_thread_while_batches_go_on(engine):
    """A server writes and hashes a snapshot on a worker thread while its event loop applies batches."""
    template = {f"f{index}": {"value": "x" * 100, "type": "str"} for index in range(20)}
    nodes = [{"id": f"n{index}", "data": {"node": {"template": template}}} for index in range(300)]
    state = engine.GraphState({"nodes": nodes, "edges": []})

    def write_field(node_id: str, field: str, value: str) -> None:
        path = ["data", "node", "template", field, "value"]
        update = {"id": node_id, "op": "set_field", "path": path, "value": value}
        state.apply([{"type": "update_nodes", "updates": [update]}])

    expected, snapshots = [], []
    for index in range(5):
        expected.append((state.to_json(), state.graph_hash()))
        snapshots.append(state.snapshot())
        write_field("n0", "f0", f"v{index}")
    seen: list[tuple[str, str]] = []

    def read() -> None:
        seen.extend((snapshot.to_json(), snapshot.graph_hash()) for snapshot in snapshots)

    def write() -> None:
        for index in range(200):
            write_field(f"n{index}", "f1", "w")

    threads = [threading.Thread(target=read), threading.Thread(target=write)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert seen == expected


def _two_nodes_and_an_edge() -> dict[str, Any]:
    def node(node_id: str) -> dict[str, Any]:
        return {"id": node_id, "data": {"node": {"template": {"t": {"value": "", "type": "str"}}}}}

    return {"nodes": [node("a"), node("b"), node("c")], "edges": [{"id": "e", "source": "a", "target": "b"}]}


def test_apply_refuses_a_graph_that_a_replay_left_with_an_edge_without_its_node(engine):
    """Replay deletes no edge with its node, so apply checks the whole graph after such a replay."""
    state = engine.GraphState(_two_nodes_and_an_edge())
    state.apply([])
    state.replay([{"type": "delete_nodes", "ids": ["a"]}])
    with pytest.raises(FlowDataValidationError) as refused:
        state.apply([])
    assert [violation["code"] for violation in refused.value.details["violations"]] == ["EDGE_ENDPOINT_INVALID"]


def test_a_replay_of_stored_operations_keeps_the_graph_checked(engine):
    """Stored operations delete a node's edges with it: the next batch does not check the whole graph again."""
    state = engine.GraphState(_two_nodes_and_an_edge())
    state.apply([])
    state.replay([{"type": "delete_nodes", "ids": ["a"]}, {"type": "delete_edges", "ids": ["e"]}])
    state.replay([{"type": "delete_nodes", "ids": ["c"]}])
    if engine is PythonEngine:
        # The Rust engine's status is not visible from Python; its own test checks it.
        assert state._state._base_checked
    path = ["data", "node", "template", "t", "value"]
    state.apply([{"type": "update_nodes", "updates": [{"id": "b", "op": "set_field", "path": path, "value": "y"}]}])
    assert [node["id"] for node in state.to_dict()["nodes"]] == ["b"]

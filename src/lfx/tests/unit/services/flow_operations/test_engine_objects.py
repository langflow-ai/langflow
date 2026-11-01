"""The engine objects' state semantics, the same for the Python engine and the Rust engine.

Staging: a staged batch returns what ``apply`` returns, readers see the
committed graph until ``keep``, ``drop`` leaves the graph as it was, and no
other batch can start while one is staged. Ownership: a result shares nothing
with the engine, and the engine shares nothing with its arguments.
"""

from __future__ import annotations

import copy
import json
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

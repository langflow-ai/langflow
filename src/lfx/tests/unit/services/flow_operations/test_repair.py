"""Repair: every direct rule has a fix, the result follows the rules, and manual rules are left alone."""

from __future__ import annotations

import copy
import math
import re

import pytest
from lfx.services.flow_operations import (
    MANUAL_CODES,
    REPAIRS,
    FlowDataValidationError,
    GraphViolationCode,
    find_graph_violations,
    repair_flow_data,
)
from lfx.services.flow_operations.edge_rules import escape_handle


def _node(node_id: str, **extra) -> dict:
    return {"id": node_id, "data": {"id": node_id, "type": "Prompt", "node": {"template": {}}}, **extra}


def _edge(edge_id, source, target) -> dict:
    return {"id": edge_id, "source": source, "target": target, "sourceHandle": "S", "targetHandle": "T"}


def _codes(result) -> list[GraphViolationCode]:
    return [fix.code for fix in result.fixes]


def test_every_rule_is_repaired_or_left_to_the_client():
    # A new rule cannot ship until someone has decided which kind it is: a direct
    # rule needs a fix, and a rule only the client can fix must have none.
    assert set(REPAIRS) | MANUAL_CODES == set(GraphViolationCode)
    assert not set(REPAIRS) & MANUAL_CODES


# --- Edges a write adds or rewires ---------------------------------------------------

EMPTY = {"nodes": [], "edges": []}
SOURCE_HANDLE = {"id": "a", "name": "out"}
TARGET_HANDLE = {"fieldName": "f", "id": "b"}


def _connectable() -> dict:
    return {
        "nodes": [
            {"id": "a", "data": {"node": {"template": {}, "outputs": [{"name": "out"}]}}},
            {"id": "b", "data": {"node": {"template": {"f": {"type": "str"}}, "outputs": []}}},
            {"id": "note", "type": "noteNode", "data": {"node": {"template": {}}}},
        ],
        "edges": [],
    }


def _handled_edge(edge_id: str, target: str = "b", target_handle: dict | None = None) -> dict:
    target_handle = target_handle or TARGET_HANDLE
    return {
        "id": edge_id,
        "source": "a",
        "target": target,
        "sourceHandle": escape_handle(SOURCE_HANDLE),
        "targetHandle": escape_handle(target_handle),
        "data": {"sourceHandle": SOURCE_HANDLE, "targetHandle": target_handle},
    }


def test_a_handle_missing_one_form_gets_it_from_the_other():
    graph = _connectable()
    edge = _handled_edge("e")
    del edge["sourceHandle"]
    del edge["data"]["targetHandle"]
    graph["edges"].append(edge)

    result = repair_flow_data(graph, base=EMPTY)

    assert result.flow_data["edges"] == [_handled_edge("e")]
    assert [(fix.code, fix.path) for fix in result.fixes] == [
        (GraphViolationCode.EDGE_HANDLE_FORM_MISSING, ("edges", 0))
    ]


def test_an_edge_that_touches_a_note_is_dropped():
    graph = _connectable()
    graph["edges"].append(_handled_edge("e", target="note"))

    result = repair_flow_data(graph, base=EMPTY)

    assert result.flow_data["edges"] == []
    assert _codes(result) == [GraphViolationCode.EDGE_TOUCHES_NOTE]


def test_a_rule_only_the_client_can_fix_is_left_and_refused():
    graph = _connectable()
    graph["edges"].append(_handled_edge("e", target_handle={"fieldName": "missing", "id": "b"}))
    graph["edges"].append(_handled_edge("e-note", target="note"))
    original = copy.deepcopy(graph)

    with pytest.raises(FlowDataValidationError) as exc_info:
        repair_flow_data(graph, base=EMPTY)

    assert [violation.to_dict()["resolution"] for violation in exc_info.value.violations] == ["manual"]
    assert exc_info.value.violations[0].code == GraphViolationCode.EDGE_HANDLE_NOT_FOUND
    assert graph == original


def test_stored_edges_the_write_leaves_alone_are_not_repaired():
    graph = _connectable()
    edge = _handled_edge("e")
    del edge["sourceHandle"]
    graph["edges"].append(edge)

    assert repair_flow_data(graph, base=copy.deepcopy(graph)).fixes == []


def test_a_valid_graph_is_returned_unchanged_with_no_fixes():
    graph = {"nodes": [_node("a"), _node("b")], "edges": [_edge("e", "a", "b")], "viewport": {"zoom": 1}}

    result = repair_flow_data(graph)

    assert result.fixes == []
    assert result.flow_data == graph
    assert result.flow_data is not graph


@pytest.mark.parametrize("flow_data", [None, [], "x"])
def test_non_object_flow_data_becomes_an_empty_flow(flow_data):
    result = repair_flow_data(flow_data)

    assert result.flow_data == {"nodes": [], "edges": []}
    assert _codes(result) == [GraphViolationCode.FLOW_DATA_NOT_OBJECT]


def test_non_list_collections_become_empty_lists():
    result = repair_flow_data({"nodes": None, "edges": "x", "description": "kept"})

    assert result.flow_data == {"nodes": [], "edges": [], "description": "kept"}
    assert _codes(result) == [GraphViolationCode.COLLECTION_NOT_LIST] * 2


def test_non_object_entries_are_dropped():
    result = repair_flow_data({"nodes": [_node("a"), 1], "edges": ["x"]})

    assert [node["id"] for node in result.flow_data["nodes"]] == ["a"]
    assert result.flow_data["edges"] == []
    assert _codes(result) == [GraphViolationCode.NODE_NOT_OBJECT, GraphViolationCode.EDGE_NOT_OBJECT]


def test_missing_node_objects_become_empty_objects():
    result = repair_flow_data({"nodes": [{"id": "a"}, {"id": "b", "data": {"node": {"template": None}}}], "edges": []})

    assert result.flow_data["nodes"][0]["data"] == {"node": {"template": {}}}
    assert result.flow_data["nodes"][1]["data"] == {"node": {"template": {}}}
    assert [fix.path for fix in result.fixes] == [
        ("nodes", 0, "data"),
        ("nodes", 0, "data", "node"),
        ("nodes", 0, "data", "node", "template"),
        ("nodes", 1, "data", "node", "template"),
    ]


def test_missing_node_id_gets_a_generated_id_in_the_editor_shape():
    node = _node("x")
    del node["id"]
    node["data"]["id"] = None

    result = repair_flow_data({"nodes": [node], "edges": []})

    (repaired,) = result.flow_data["nodes"]
    assert repaired["id"].startswith("Prompt-")
    assert len(repaired["id"]) == len("Prompt-") + 5
    assert repaired["data"]["id"] == repaired["id"]
    assert _codes(result) == [GraphViolationCode.NODE_ID_MISSING]


def test_duplicate_node_ids_keep_the_first_node_and_its_edges():
    graph = {"nodes": [_node("a"), _node("a", position={"x": 1}), _node("b")], "edges": [_edge("e", "a", "b")]}

    result = repair_flow_data(graph)

    first, second, _ = result.flow_data["nodes"]
    assert first["id"] == "a"
    assert second["id"] != "a"
    assert second["data"]["id"] == second["id"]
    assert result.flow_data["edges"] == [_edge("e", "a", "b")]
    assert _codes(result) == [GraphViolationCode.NODE_ID_DUPLICATE]


def test_edges_to_unknown_nodes_are_dropped():
    graph = {"nodes": [_node("a")], "edges": [_edge("e1", "a", "zz"), {"id": "e2", "target": "a"}]}

    result = repair_flow_data(graph)

    assert result.flow_data["edges"] == []
    assert _codes(result) == [GraphViolationCode.EDGE_ENDPOINT_INVALID] * 2


def test_missing_and_duplicate_edge_ids_are_opaque_like_the_editor():
    no_id = _edge("x", "a", "b")
    del no_id["id"]
    graph = {"nodes": [_node("a"), _node("b")], "edges": [_edge("e", "a", "b"), _edge("e", "b", "a"), no_id]}

    result = repair_flow_data(graph)

    ids = [edge["id"] for edge in result.flow_data["edges"]]
    assert ids[0] == "e"
    assert all(re.fullmatch(r"e-[0-9A-Za-z]{21}", edge_id) for edge_id in ids[1:])
    assert len(set(ids)) == 3
    assert _codes(result) == [GraphViolationCode.EDGE_ID_DUPLICATE, GraphViolationCode.EDGE_ID_MISSING]


def test_non_finite_numbers_become_null():
    graph = {"nodes": [_node("a", position={"x": math.nan, "y": 1})], "edges": [], "zoom": math.inf}

    result = repair_flow_data(graph)

    assert result.flow_data["nodes"][0]["position"] == {"x": None, "y": 1}
    assert result.flow_data["zoom"] is None
    assert sorted(fix.path for fix in result.fixes) == [("nodes", 0, "position", "x"), ("zoom",)]


def test_repair_is_deterministic_and_leaves_the_input_alone():
    graph = {"nodes": [{"data": {"type": "Prompt"}}, _node("a"), _node("a")], "edges": [{"source": "a", "target": "a"}]}
    original = copy.deepcopy(graph)

    first = repair_flow_data(graph)
    second = repair_flow_data(graph)

    # Node and row ids are derived from content; edge ids are opaque and random.
    assert first.flow_data["nodes"] == second.flow_data["nodes"]
    assert [{**edge, "id": None} for edge in first.flow_data["edges"]] == [
        {**edge, "id": None} for edge in second.flow_data["edges"]
    ]
    assert graph == original


def test_a_badly_broken_graph_comes_out_following_every_rule():
    graph = {
        "nodes": [None, {"id": 3}, {"id": "a", "data": []}, {"id": "a"}, {"data": {"node": {"template": 1}}}],
        "edges": [{"id": "e"}, {"id": "e", "source": "a", "target": "a", "w": math.nan}, 7],
    }

    result = repair_flow_data(graph)

    assert find_graph_violations(result.flow_data) == []
    assert {fix.code for fix in result.fixes} >= {
        GraphViolationCode.NODE_NOT_OBJECT,
        GraphViolationCode.NODE_ID_MISSING,
        GraphViolationCode.NODE_ID_DUPLICATE,
        GraphViolationCode.NODE_DATA_NOT_OBJECT,
        GraphViolationCode.EDGE_NOT_OBJECT,
        GraphViolationCode.EDGE_ENDPOINT_INVALID,
        GraphViolationCode.NON_FINITE_NUMBER,
    }
    dropped = next(fix for fix in result.fixes if fix.code is GraphViolationCode.NODE_NOT_OBJECT)
    assert dropped.to_dict() == {"code": "NODE_NOT_OBJECT", "path": ["nodes", 0], "action": "dropped the entry"}

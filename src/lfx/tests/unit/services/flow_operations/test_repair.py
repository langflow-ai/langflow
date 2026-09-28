"""Repair: every rule the engine enforces has a fix, and the result follows the rules."""

from __future__ import annotations

import copy
import math

import pytest
from lfx.services.flow_operations import (
    REPAIRS,
    GraphViolationCode,
    find_graph_violations,
    repair_flow_data,
)


def _node(node_id: str, **extra) -> dict:
    return {"id": node_id, "data": {"id": node_id, "type": "Prompt", "node": {"template": {}}}, **extra}


def _edge(edge_id, source, target) -> dict:
    return {"id": edge_id, "source": source, "target": target, "sourceHandle": "S", "targetHandle": "T"}


def _codes(result) -> list[GraphViolationCode]:
    return [fix.code for fix in result.fixes]


def test_every_rule_has_a_repair():
    # A new engine rule cannot ship without a way out for flows that break it.
    assert set(REPAIRS) == set(GraphViolationCode)


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


def test_missing_and_duplicate_edge_ids_are_generated_like_the_editor():
    no_id = _edge("x", "a", "b")
    del no_id["id"]
    graph = {"nodes": [_node("a"), _node("b")], "edges": [_edge("e", "a", "b"), _edge("e", "b", "a"), no_id]}

    result = repair_flow_data(graph)

    ids = [edge["id"] for edge in result.flow_data["edges"]]
    assert ids == ["e", "reactflow__edge-bS-aT", "reactflow__edge-aS-bT"]
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

    assert first.flow_data == second.flow_data
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

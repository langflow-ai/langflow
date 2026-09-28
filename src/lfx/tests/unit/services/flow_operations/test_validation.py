"""Graph rules: every violation is reported with a stable code and path."""

from __future__ import annotations

import math

import pytest
from lfx.services.flow_operations import (
    FlowDataValidationError,
    GraphViolationCode,
    find_graph_violations,
    validate_flow_data,
)


def _node(node_id: str) -> dict:
    return {"id": node_id, "data": {"node": {"template": {}}}}


def _graph() -> dict:
    return {"nodes": [_node("a"), _node("b")], "edges": [{"id": "e", "source": "a", "target": "b"}]}


def _codes(flow_data) -> list[tuple[GraphViolationCode, tuple]]:
    return [(violation.code, violation.path) for violation in find_graph_violations(flow_data)]


def test_a_valid_graph_has_no_violations():
    assert find_graph_violations(_graph()) == []
    validate_flow_data(_graph())


@pytest.mark.parametrize("flow_data", [None, [], "flow"])
def test_flow_data_must_be_an_object(flow_data):
    assert _codes(flow_data) == [(GraphViolationCode.FLOW_DATA_NOT_OBJECT, ())]


def test_collections_must_be_lists():
    assert _codes({"nodes": None, "edges": {}}) == [
        (GraphViolationCode.COLLECTION_NOT_LIST, ("nodes",)),
        (GraphViolationCode.COLLECTION_NOT_LIST, ("edges",)),
    ]


def test_entries_must_be_objects():
    assert _codes({"nodes": ["x"], "edges": [3]}) == [
        (GraphViolationCode.NODE_NOT_OBJECT, ("nodes", 0)),
        (GraphViolationCode.EDGE_NOT_OBJECT, ("edges", 0)),
    ]


def test_node_ids_must_be_present_and_unique():
    graph = _graph()
    graph["nodes"] += [_node("a"), {"id": "", "data": {"node": {"template": {}}}}]

    assert _codes(graph) == [
        (GraphViolationCode.NODE_ID_DUPLICATE, ("nodes", 2, "id")),
        (GraphViolationCode.NODE_ID_MISSING, ("nodes", 3, "id")),
    ]


def test_edge_ids_must_be_present_and_unique():
    graph = _graph()
    graph["edges"] += [{"id": "e", "source": "a", "target": "b"}, {"source": "a", "target": "b"}]

    assert _codes(graph) == [
        (GraphViolationCode.EDGE_ID_DUPLICATE, ("edges", 1, "id")),
        (GraphViolationCode.EDGE_ID_MISSING, ("edges", 2, "id")),
    ]


def test_edge_endpoints_must_name_existing_nodes():
    graph = _graph()
    graph["edges"] = [{"id": "e1", "target": "b"}, {"id": "e2", "source": "a", "target": "zz"}]

    assert _codes(graph) == [
        (GraphViolationCode.EDGE_ENDPOINT_INVALID, ("edges", 0, "source")),
        (GraphViolationCode.EDGE_ENDPOINT_INVALID, ("edges", 1, "target")),
    ]


@pytest.mark.parametrize(
    ("data", "path"),
    [
        (None, ("data",)),
        ({"node": []}, ("data", "node")),
        ({"node": {}}, ("data", "node", "template")),
        ({"node": {"template": "x"}}, ("data", "node", "template")),
    ],
)
def test_node_data_objects_must_be_objects(data, path):
    graph = _graph()
    graph["nodes"][0]["data"] = data

    assert _codes(graph) == [(GraphViolationCode.NODE_DATA_NOT_OBJECT, ("nodes", 0, *path))]


def test_non_finite_numbers_are_violations_unless_values_are_skipped():
    graph = _graph()
    graph["nodes"][0]["position"] = {"x": math.nan, "y": math.inf}

    assert _codes(graph) == [
        (GraphViolationCode.NON_FINITE_NUMBER, ("nodes", 0, "position", "x")),
        (GraphViolationCode.NON_FINITE_NUMBER, ("nodes", 0, "position", "y")),
    ]
    assert find_graph_violations(graph, check_values=False) == []


def test_validate_raises_with_every_violation():
    graph = _graph()
    graph["nodes"].append(_node("a"))
    graph["edges"].append({"id": "e2", "source": "a", "target": "zz"})

    with pytest.raises(FlowDataValidationError) as exc_info:
        validate_flow_data(graph)

    assert exc_info.value.code == "FLOW_GRAPH_INVALID"
    assert [violation.code for violation in exc_info.value.violations] == [
        GraphViolationCode.NODE_ID_DUPLICATE,
        GraphViolationCode.EDGE_ENDPOINT_INVALID,
    ]
    assert exc_info.value.violations[0].to_dict() == {
        "code": "NODE_ID_DUPLICATE",
        "path": ["nodes", 2, "id"],
        "message": "duplicate node id",
    }

"""Story 2.2 — xyflow diagram schema + validator.

`validate_diagram` is a pure function over an xyflow graph, so these tests need
no DB or LLM: they build dicts and assert that a well-formed graph passes and
each malformed graph is rejected with a clear `DiagramValidationError`.
"""

import copy

import pytest
from langflow.lothal.diagram import (
    DiagramGraph,
    DiagramValidationError,
    validate_diagram,
)


def _graph() -> dict:
    """A minimal valid graph: 2 nodes, 3 edges, all ids resolvable."""
    return {
        "nodes": [
            {"id": "user", "type": "actorNode", "position": {"x": 0, "y": 0}, "data": {"label": "User"}},
            {"id": "api", "type": "systemNode", "position": {"x": 200, "y": 0}, "data": {"label": "API"}},
        ],
        "edges": [
            {"id": "e1", "source": "user", "target": "api", "data": {"order": 0}},
            {"id": "e2", "source": "api", "target": "user", "animated": True, "data": {"order": 1}},
            {"id": "e3", "source": "user", "target": "api", "data": {"order": 2}},
        ],
    }


def test_valid_graph_passes_and_returns_model():
    result = validate_diagram(_graph())

    assert isinstance(result, DiagramGraph)
    assert [n.id for n in result.nodes] == ["user", "api"]
    assert [e.data.order for e in result.edges] == [0, 1, 2]
    # animated defaults to False (synchronous/solid) when omitted.
    assert result.edges[0].animated is False
    assert result.edges[1].animated is True


def test_already_parsed_graph_is_idempotent():
    once = validate_diagram(_graph())
    twice = validate_diagram(once)

    assert twice == once


def test_optional_render_hints_are_kept():
    graph = _graph()
    graph["nodes"][0]["data"].update({"kind": "person", "note": "the end user"})
    graph["edges"][0]["data"].update({"label": "login", "kind": "auth"})

    result = validate_diagram(graph)

    assert result.nodes[0].data.kind == "person"
    assert result.nodes[0].data.note == "the end user"
    assert result.edges[0].data.label == "login"
    assert result.edges[0].data.kind == "auth"


def test_too_few_nodes_rejected():
    graph = _graph()
    graph["nodes"] = graph["nodes"][:1]
    graph["edges"] = [{"id": "e1", "source": "user", "target": "user", "data": {"order": 0}}] * 3

    with pytest.raises(DiagramValidationError, match="at least 2 nodes"):
        validate_diagram(graph)


def test_too_few_edges_rejected():
    graph = _graph()
    graph["edges"] = graph["edges"][:2]

    with pytest.raises(DiagramValidationError, match="at least 3 edges"):
        validate_diagram(graph)


def test_duplicate_node_id_rejected():
    graph = _graph()
    graph["nodes"][1]["id"] = "user"

    with pytest.raises(DiagramValidationError, match="Duplicate node id"):
        validate_diagram(graph)


def test_dangling_edge_source_rejected():
    graph = _graph()
    graph["edges"][0]["source"] = "ghost"

    with pytest.raises(DiagramValidationError, match="unknown node"):
        validate_diagram(graph)


def test_dangling_edge_target_rejected():
    graph = _graph()
    graph["edges"][0]["target"] = "ghost"

    with pytest.raises(DiagramValidationError, match="unknown node"):
        validate_diagram(graph)


def test_unknown_node_type_rejected():
    graph = _graph()
    graph["nodes"][0]["type"] = "decisionNode"

    with pytest.raises(DiagramValidationError, match="Malformed diagram graph"):
        validate_diagram(graph)


def test_missing_position_rejected():
    graph = _graph()
    del graph["nodes"][0]["position"]

    with pytest.raises(DiagramValidationError, match="Malformed diagram graph"):
        validate_diagram(graph)


def test_non_numeric_position_rejected():
    graph = _graph()
    graph["nodes"][0]["position"]["x"] = "left"

    with pytest.raises(DiagramValidationError, match="Malformed diagram graph"):
        validate_diagram(graph)


def test_missing_edge_order_rejected():
    graph = _graph()
    del graph["edges"][0]["data"]["order"]

    with pytest.raises(DiagramValidationError, match="Malformed diagram graph"):
        validate_diagram(graph)


def test_missing_node_label_rejected():
    graph = _graph()
    del graph["nodes"][0]["data"]["label"]

    with pytest.raises(DiagramValidationError, match="Malformed diagram graph"):
        validate_diagram(graph)


def test_validation_does_not_mutate_input():
    graph = _graph()
    before = copy.deepcopy(graph)

    validate_diagram(graph)

    assert graph == before

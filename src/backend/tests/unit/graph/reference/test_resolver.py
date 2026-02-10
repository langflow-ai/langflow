# src/backend/tests/unit/graph/reference/test_resolver.py
from unittest.mock import MagicMock

import pytest
from lfx.graph.reference.resolver import ReferenceResolutionError, resolve_references


def test_resolve_single_reference():
    # Mock graph with vertex
    mock_vertex = MagicMock()
    mock_vertex.outputs_map = {"response": {"data": "hello"}}

    mock_graph = MagicMock()
    mock_graph.get_vertex_by_slug.return_value = mock_vertex

    text = "Result: @HTTPRequest_1.response"
    result = resolve_references(text, mock_graph)

    assert result == "Result: {'data': 'hello'}"
    mock_graph.get_vertex_by_slug.assert_called_once_with("HTTPRequest_1")


def test_resolve_reference_with_dot_path():
    mock_vertex = MagicMock()
    mock_vertex.outputs_map = {"response": {"data": {"name": "John"}}}

    mock_graph = MagicMock()
    mock_graph.get_vertex_by_slug.return_value = mock_vertex

    text = "Name: @HTTPRequest_1.response.data.name"
    result = resolve_references(text, mock_graph)

    assert result == "Name: John"


def test_resolve_multiple_references():
    mock_vertex1 = MagicMock()
    mock_vertex1.outputs_map = {"output": "first"}

    mock_vertex2 = MagicMock()
    mock_vertex2.outputs_map = {"output": "second"}

    mock_graph = MagicMock()
    mock_graph.get_vertex_by_slug.side_effect = lambda slug: {
        "Node1": mock_vertex1,
        "Node2": mock_vertex2,
    }.get(slug)

    text = "@Node1.output and @Node2.output"
    result = resolve_references(text, mock_graph)

    assert result == "first and second"


def test_resolve_no_references():
    mock_graph = MagicMock()

    text = "No references here"
    result = resolve_references(text, mock_graph)

    assert result == "No references here"
    mock_graph.get_vertex_by_slug.assert_not_called()


def test_resolve_missing_node_raises():
    mock_graph = MagicMock()
    mock_graph.get_vertex_by_slug.return_value = None

    text = "@MissingNode.output"

    with pytest.raises(ReferenceResolutionError, match="Node 'MissingNode' not found"):
        resolve_references(text, mock_graph)


def test_resolve_missing_output_raises():
    mock_vertex = MagicMock()
    mock_vertex.outputs_map = {}
    mock_vertex.id = "vertex-123"

    mock_graph = MagicMock()
    mock_graph.get_vertex_by_slug.return_value = mock_vertex

    text = "@Node.missing_output"

    with pytest.raises(ReferenceResolutionError, match="Output 'missing_output' not found"):
        resolve_references(text, mock_graph)

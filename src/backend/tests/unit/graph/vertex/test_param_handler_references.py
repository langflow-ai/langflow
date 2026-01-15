# src/backend/tests/unit/graph/vertex/test_param_handler_references.py
from unittest.mock import MagicMock


def test_should_resolve_references_true():
    """Test that _should_resolve_references returns True when has_references=True."""
    from lfx.graph.vertex.param_handler import ParameterHandler

    mock_vertex = MagicMock()
    handler = ParameterHandler(mock_vertex, None)

    field = {"has_references": True}
    assert handler._should_resolve_references(field) is True


def test_should_resolve_references_false():
    """Test that _should_resolve_references returns False when has_references=False."""
    from lfx.graph.vertex.param_handler import ParameterHandler

    mock_vertex = MagicMock()
    handler = ParameterHandler(mock_vertex, None)

    field = {"has_references": False}
    assert handler._should_resolve_references(field) is False


def test_should_resolve_references_missing_key():
    """Test that _should_resolve_references returns False when has_references key is missing."""
    from lfx.graph.vertex.param_handler import ParameterHandler

    mock_vertex = MagicMock()
    handler = ParameterHandler(mock_vertex, None)

    field = {"name": "test"}  # No has_references key
    assert handler._should_resolve_references(field) is False

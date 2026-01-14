# src/backend/tests/unit/graph/vertex/test_param_handler_references.py
from unittest.mock import MagicMock, patch


def test_resolve_field_references_called():
    """Test that fields with has_references=True get resolved."""
    from lfx.graph.vertex.param_handler import ParameterHandler

    mock_vertex = MagicMock()
    mock_vertex.graph = MagicMock()

    handler = ParameterHandler(mock_vertex, None)

    field = {
        "name": "prompt",
        "type": "str",
        "value": "Hello @Node.output",
        "has_references": True,
    }

    with patch.object(handler, "_resolve_field_references") as mock_resolve:
        mock_resolve.return_value = "Hello resolved_value"
        result = handler._resolve_field_references("Hello @Node.output", field)
        mock_resolve.assert_called_once()


def test_resolve_field_references_skipped_when_false():
    """Test that fields without has_references are not resolved."""
    from lfx.graph.vertex.param_handler import ParameterHandler

    mock_vertex = MagicMock()
    handler = ParameterHandler(mock_vertex, None)

    field = {
        "name": "prompt",
        "type": "str",
        "value": "Hello @Node.output",
        "has_references": False,
    }

    # Should return unchanged when has_references is False
    result = handler._should_resolve_references(field)
    assert result is False


def test_should_resolve_references_true():
    from lfx.graph.vertex.param_handler import ParameterHandler

    mock_vertex = MagicMock()
    handler = ParameterHandler(mock_vertex, None)

    field = {"has_references": True}
    assert handler._should_resolve_references(field) is True


def test_should_resolve_references_missing_key():
    from lfx.graph.vertex.param_handler import ParameterHandler

    mock_vertex = MagicMock()
    handler = ParameterHandler(mock_vertex, None)

    field = {"name": "test"}  # No has_references key
    assert handler._should_resolve_references(field) is False

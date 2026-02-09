# src/lfx/tests/unit/graph/reference/test_resolver.py
import json
from unittest.mock import MagicMock

import pytest
from lfx.graph.reference.resolver import (
    VARS_SLUG,
    ReferenceResolutionError,
    _extract_text_value,
    resolve_references,
)
from lfx.schema.data import Data
from lfx.schema.message import Message


class TestExtractTextValue:
    def test_extract_from_none(self):
        result = _extract_text_value(None)
        assert result == ""

    def test_extract_from_message(self):
        msg = Message(text="Hello world")
        result = _extract_text_value(msg)
        assert result == "Hello world"

    def test_extract_from_message_with_none_text(self):
        msg = Message(text=None)
        result = _extract_text_value(msg)
        assert result == ""

    def test_extract_from_data(self):
        data = Data(data={"key": "value", "number": 42})
        result = _extract_text_value(data)
        # Should be JSON stringified
        parsed = json.loads(result)
        assert parsed == {"key": "value", "number": 42}

    def test_extract_from_data_with_nested_structure(self):
        data = Data(data={"nested": {"deep": [1, 2, 3]}})
        result = _extract_text_value(data)
        parsed = json.loads(result)
        assert parsed == {"nested": {"deep": [1, 2, 3]}}

    def test_extract_from_string(self):
        result = _extract_text_value("plain text")
        assert result == "plain text"

    def test_extract_from_int(self):
        result = _extract_text_value(42)
        assert result == "42"

    def test_extract_from_float(self):
        result = _extract_text_value(3.14)
        assert result == "3.14"

    def test_extract_from_bool(self):
        bool_value = True
        result = _extract_text_value(bool_value)
        assert result == "True"

    def test_extract_from_object_with_text_attribute(self):
        obj = MagicMock()
        obj.text = "text from attribute"
        result = _extract_text_value(obj)
        assert result == "text from attribute"

    def test_extract_from_list(self):
        result = _extract_text_value([1, 2, 3])
        assert result == "[1, 2, 3]"


class TestResolveReferences:
    def _create_mock_graph(self, vertices_by_slug: dict):
        """Create a mock graph with vertices accessible by slug."""
        graph = MagicMock()

        def get_vertex_by_slug(slug):
            return vertices_by_slug.get(slug)

        graph.get_vertex_by_slug = get_vertex_by_slug
        return graph

    def _create_mock_vertex(self, outputs: dict):
        """Create a mock vertex with specified outputs."""
        vertex = MagicMock()
        vertex.outputs_map = outputs
        return vertex

    def _create_mock_output(self, value):
        """Create a mock output with a value."""
        output = MagicMock()
        output.value = value
        return output

    def test_resolve_simple_reference(self):
        output = self._create_mock_output("resolved value")
        vertex = self._create_mock_vertex({"text": output})
        graph = self._create_mock_graph({"ChatInput": vertex})

        text = "Hello @ChatInput.text!"
        result = resolve_references(text, graph)
        assert result == "Hello resolved value!"

    def test_resolve_multiple_references(self):
        output1 = self._create_mock_output("Alice")
        output2 = self._create_mock_output("Bob")
        vertex1 = self._create_mock_vertex({"name": output1})
        vertex2 = self._create_mock_vertex({"name": output2})
        graph = self._create_mock_graph({"User1": vertex1, "User2": vertex2})

        text = "@User1.name and @User2.name"
        result = resolve_references(text, graph)
        assert result == "Alice and Bob"

    def test_resolve_message_reference(self):
        msg = Message(text="Hello from message")
        output = self._create_mock_output(msg)
        vertex = self._create_mock_vertex({"message": output})
        graph = self._create_mock_graph({"ChatInput": vertex})

        text = "Message: @ChatInput.message"
        result = resolve_references(text, graph)
        assert result == "Message: Hello from message"

    def test_resolve_data_reference(self):
        data = Data(data={"status": "ok"})
        output = self._create_mock_output(data)
        vertex = self._create_mock_vertex({"result": output})
        graph = self._create_mock_graph({"API": vertex})

        text = "Result: @API.result"
        result = resolve_references(text, graph)
        # Should be JSON string
        assert '"status"' in result
        assert '"ok"' in result

    def test_resolve_no_references(self):
        graph = self._create_mock_graph({})
        text = "No references here"
        result = resolve_references(text, graph)
        assert result == "No references here"

    def test_resolve_node_not_found(self):
        graph = self._create_mock_graph({})
        text = "@NonExistent.output"
        with pytest.raises(ReferenceResolutionError) as exc_info:
            resolve_references(text, graph)
        assert "NonExistent" in str(exc_info.value)
        assert "not found" in str(exc_info.value)

    def test_resolve_output_not_found(self):
        vertex = self._create_mock_vertex({})
        vertex.id = "vertex-123"
        graph = self._create_mock_graph({"Node": vertex})

        text = "@Node.missing_output"
        with pytest.raises(ReferenceResolutionError) as exc_info:
            resolve_references(text, graph)
        assert "missing_output" in str(exc_info.value)
        assert "not found" in str(exc_info.value)

    def test_resolve_with_dot_path(self):
        data = {"user": {"name": "John"}}
        output = self._create_mock_output(data)
        vertex = self._create_mock_vertex({"data": output})
        graph = self._create_mock_graph({"API": vertex})

        text = "Name: @API.data.user.name"
        result = resolve_references(text, graph)
        assert result == "Name: John"

    def test_resolve_with_array_index(self):
        data = {"items": ["first", "second", "third"]}
        output = self._create_mock_output(data)
        vertex = self._create_mock_vertex({"data": output})
        graph = self._create_mock_graph({"API": vertex})

        text = "Second item: @API.data.items[1]"
        result = resolve_references(text, graph)
        assert result == "Second item: second"

    def test_resolve_empty_string(self):
        graph = self._create_mock_graph({})
        result = resolve_references("", graph)
        assert result == ""

    def test_resolve_output_without_value_attribute(self):
        # Test case where output doesn't have .value attribute
        vertex = self._create_mock_vertex({"direct": "direct value"})
        graph = self._create_mock_graph({"Node": vertex})

        text = "@Node.direct"
        result = resolve_references(text, graph)
        assert result == "direct value"

    def test_resolve_overlapping_references(self):
        """Longer references should be resolved before shorter prefixes."""
        data = {"user": {"name": "John"}}
        output = self._create_mock_output(data)
        vertex = self._create_mock_vertex({"data": output})
        graph = self._create_mock_graph({"API": vertex})

        # Both @API.data.user.name and @API.data appear — the longer one must be resolved first
        text = "Raw: @API.data, Full: @API.data.user.name"
        result = resolve_references(text, graph)
        assert "John" in result
        # @API.data resolves to the dict (str() representation)
        assert "user" in result

    def test_resolve_direct_array_index(self):
        """References with direct array index after output should resolve."""
        items = ["first", "second"]
        output = self._create_mock_output(items)
        vertex = self._create_mock_vertex({"items": output})
        graph = self._create_mock_graph({"List": vertex})

        text = "Item: @List.items[0]"
        result = resolve_references(text, graph)
        assert result == "Item: first"

    def test_resolve_invalid_dot_path_raises(self):
        """Invalid dot path should raise ReferenceResolutionError."""
        data = {"user": {"name": "John"}}
        output = self._create_mock_output(data)
        vertex = self._create_mock_vertex({"data": output})
        graph = self._create_mock_graph({"API": vertex})

        text = "@API.data.user.nonexistent"
        with pytest.raises(ReferenceResolutionError, match="Failed to resolve path"):
            resolve_references(text, graph)

    def test_resolve_invalid_array_index_raises(self):
        """Out-of-range array index in dot path should raise ReferenceResolutionError."""
        data = {"items": ["a", "b"]}
        output = self._create_mock_output(data)
        vertex = self._create_mock_vertex({"data": output})
        graph = self._create_mock_graph({"API": vertex})

        text = "@API.data.items[99]"
        with pytest.raises(ReferenceResolutionError, match="Failed to resolve path"):
            resolve_references(text, graph)


class TestGlobalVariableReferences:
    """Tests for @Vars.variable_name resolution."""

    def _create_mock_graph(self, vertices_by_slug=None):
        graph = MagicMock()
        vertices_by_slug = vertices_by_slug or {}
        graph.get_vertex_by_slug = lambda slug: vertices_by_slug.get(slug)
        return graph

    def _create_mock_output(self, value):
        output = MagicMock()
        output.value = value
        return output

    def _create_mock_vertex(self, outputs):
        vertex = MagicMock()
        vertex.outputs_map = outputs
        return vertex

    def test_globals_slug_constant(self):
        assert VARS_SLUG == "Vars"

    def test_resolve_global_variable(self):
        graph = self._create_mock_graph()
        global_vars = {"my_var": "test-value", "model": "gpt-4"}

        text = "Using @Vars.model"
        result = resolve_references(text, graph, global_variables=global_vars)
        assert result == "Using gpt-4"

    def test_resolve_global_variable_alone(self):
        graph = self._create_mock_graph()
        global_vars = {"greeting": "hello"}

        result = resolve_references("@Vars.greeting", graph, global_variables=global_vars)
        assert result == "hello"

    def test_resolve_global_variable_missing(self):
        graph = self._create_mock_graph()
        global_vars = {"existing": "value"}

        with pytest.raises(ReferenceResolutionError, match="Global variable 'missing'"):
            resolve_references("@Vars.missing", graph, global_variables=global_vars)

    def test_resolve_global_variable_no_dict(self):
        """Should raise when global_variables is None."""
        graph = self._create_mock_graph()

        with pytest.raises(ReferenceResolutionError, match="Global variables are not available"):
            resolve_references("@Vars.var", graph, global_variables=None)

    def test_resolve_global_variable_empty_dict(self):
        graph = self._create_mock_graph()

        with pytest.raises(ReferenceResolutionError, match="Global variable"):
            resolve_references("@Vars.var", graph, global_variables={})

    def test_resolve_mixed_node_and_global(self):
        """Both @Node.output and @Vars.var in same text."""
        output = self._create_mock_output("Alice")
        vertex = self._create_mock_vertex({"name": output})
        graph = self._create_mock_graph({"User": vertex})
        global_vars = {"greeting": "Hello"}

        text = "@Vars.greeting, @User.name!"
        result = resolve_references(text, graph, global_variables=global_vars)
        assert result == "Hello, Alice!"

    def test_resolve_multiple_global_variables(self):
        graph = self._create_mock_graph()
        global_vars = {"first": "A", "second": "B"}

        text = "@Vars.first and @Vars.second"
        result = resolve_references(text, graph, global_variables=global_vars)
        assert result == "A and B"

    def test_resolve_global_variable_with_dot_path(self):
        """Global variable value is a dict, traversed via dot path."""
        graph = self._create_mock_graph()
        global_vars = {"config": {"model": "gpt-4", "temperature": 0.7}}

        text = "Model: @Vars.config.model"
        result = resolve_references(text, graph, global_variables=global_vars)
        assert result == "Model: gpt-4"

    def test_global_variable_does_not_go_through_vertex_lookup(self):
        """@Vars.x should NOT call graph.get_vertex_by_slug."""
        graph = MagicMock()
        graph.get_vertex_by_slug = MagicMock(return_value=None)
        global_vars = {"x": "value"}

        resolve_references("@Vars.x", graph, global_variables=global_vars)
        graph.get_vertex_by_slug.assert_not_called()

# src/lfx/tests/unit/graph/reference/test_resolver.py
import json
from unittest.mock import MagicMock

import pytest
from lfx.graph.reference.resolver import (
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

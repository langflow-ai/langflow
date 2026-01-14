# src/lfx/tests/unit/graph/reference/test_integration.py
"""Integration tests for the complete reference resolution flow.

These tests verify that @references are correctly resolved during
parameter processing, simulating the flow from frontend to backend.
"""

from unittest.mock import MagicMock

from lfx.graph.reference import resolve_references
from lfx.graph.vertex.param_handler import ParameterHandler
from lfx.schema.message import Message


class TestReferenceResolutionIntegration:
    """Integration tests for reference resolution in parameter handling."""

    def _create_mock_graph(self, vertices_by_slug: dict):
        """Create a mock graph with vertices accessible by slug."""
        graph = MagicMock()
        graph.get_vertex_by_slug = lambda slug: vertices_by_slug.get(slug)
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

    def test_param_handler_resolves_string_reference(self):
        """Test that param_handler resolves @references in string fields."""
        # Set up upstream vertex with output
        upstream_output = self._create_mock_output("Hello from upstream")
        upstream_vertex = self._create_mock_vertex({"message": upstream_output})
        graph = self._create_mock_graph({"ChatInput": upstream_vertex})

        # Create mock target vertex with template containing reference
        mock_vertex = MagicMock()
        mock_vertex.graph = graph
        mock_vertex.display_name = "TestComponent"
        mock_vertex.data = {
            "node": {
                "template": {
                    "prompt": {
                        "type": "str",
                        "value": "User said: @ChatInput.message",
                        "has_references": True,
                        "show": True,
                    }
                }
            }
        }

        handler = ParameterHandler(mock_vertex, storage_service=None)
        params, _ = handler.process_field_parameters()

        assert params["prompt"] == "User said: Hello from upstream"

    def test_param_handler_resolves_message_reference(self):
        """Test that Message objects are resolved to their text content."""
        # Set up upstream vertex with Message output
        message = Message(text="This is a message")
        upstream_output = self._create_mock_output(message)
        upstream_vertex = self._create_mock_vertex({"output": upstream_output})
        graph = self._create_mock_graph({"MessageSource": upstream_vertex})

        mock_vertex = MagicMock()
        mock_vertex.graph = graph
        mock_vertex.display_name = "TestComponent"
        mock_vertex.data = {
            "node": {
                "template": {
                    "input_text": {
                        "type": "str",
                        "value": "Received: @MessageSource.output",
                        "has_references": True,
                        "show": True,
                    }
                }
            }
        }

        handler = ParameterHandler(mock_vertex, storage_service=None)
        params, _ = handler.process_field_parameters()

        assert params["input_text"] == "Received: This is a message"

    def test_param_handler_resolves_multiple_references(self):
        """Test resolving multiple references in a single field."""
        user_output = self._create_mock_output("Alice")
        greeting_output = self._create_mock_output("Hello")
        user_vertex = self._create_mock_vertex({"name": user_output})
        greeting_vertex = self._create_mock_vertex({"text": greeting_output})
        graph = self._create_mock_graph(
            {
                "UserInput": user_vertex,
                "GreetingGenerator": greeting_vertex,
            }
        )

        mock_vertex = MagicMock()
        mock_vertex.graph = graph
        mock_vertex.display_name = "TestComponent"
        mock_vertex.data = {
            "node": {
                "template": {
                    "combined": {
                        "type": "str",
                        "value": "@GreetingGenerator.text, @UserInput.name!",
                        "has_references": True,
                        "show": True,
                    }
                }
            }
        }

        handler = ParameterHandler(mock_vertex, storage_service=None)
        params, _ = handler.process_field_parameters()

        assert params["combined"] == "Hello, Alice!"

    def test_param_handler_skips_fields_without_has_references(self):
        """Test that fields without has_references=True are not resolved."""
        upstream_output = self._create_mock_output("Should not resolve")
        upstream_vertex = self._create_mock_vertex({"output": upstream_output})
        graph = self._create_mock_graph({"Node": upstream_vertex})

        mock_vertex = MagicMock()
        mock_vertex.graph = graph
        mock_vertex.display_name = "TestComponent"
        mock_vertex.data = {
            "node": {
                "template": {
                    "raw_text": {
                        "type": "str",
                        "value": "@Node.output",
                        "has_references": False,  # Explicitly disabled
                        "show": True,
                    }
                }
            }
        }

        handler = ParameterHandler(mock_vertex, storage_service=None)
        params, _ = handler.process_field_parameters()

        # Value should remain unchanged (not resolved)
        assert params["raw_text"] == "@Node.output"

    def test_param_handler_handles_missing_node(self):
        """Test that missing node reference logs warning but doesn't crash."""
        graph = self._create_mock_graph({})  # No vertices

        mock_vertex = MagicMock()
        mock_vertex.graph = graph
        mock_vertex.display_name = "TestComponent"
        mock_vertex.data = {
            "node": {
                "template": {
                    "text": {
                        "type": "str",
                        "value": "@NonExistent.output",
                        "has_references": True,
                        "show": True,
                    }
                }
            }
        }

        handler = ParameterHandler(mock_vertex, storage_service=None)
        # Should not raise, but should log warning
        params, _ = handler.process_field_parameters()

        # Value remains unchanged since resolution failed
        assert params["text"] == "@NonExistent.output"

    def test_param_handler_resolves_dot_path_reference(self):
        """Test resolving reference with dot path accessor."""
        data_output = self._create_mock_output({"user": {"name": "Bob"}})
        upstream_vertex = self._create_mock_vertex({"data": data_output})
        graph = self._create_mock_graph({"API": upstream_vertex})

        mock_vertex = MagicMock()
        mock_vertex.graph = graph
        mock_vertex.display_name = "TestComponent"
        mock_vertex.data = {
            "node": {
                "template": {
                    "name": {
                        "type": "str",
                        "value": "Name is @API.data.user.name",
                        "has_references": True,
                        "show": True,
                    }
                }
            }
        }

        handler = ParameterHandler(mock_vertex, storage_service=None)
        params, _ = handler.process_field_parameters()

        assert params["name"] == "Name is Bob"

    def test_param_handler_resolves_array_index_reference(self):
        """Test resolving reference with array index accessor."""
        list_output = self._create_mock_output({"items": ["first", "second", "third"]})
        upstream_vertex = self._create_mock_vertex({"list": list_output})
        graph = self._create_mock_graph({"ListSource": upstream_vertex})

        mock_vertex = MagicMock()
        mock_vertex.graph = graph
        mock_vertex.display_name = "TestComponent"
        mock_vertex.data = {
            "node": {
                "template": {
                    "item": {
                        "type": "str",
                        "value": "Second item: @ListSource.list.items[1]",
                        "has_references": True,
                        "show": True,
                    }
                }
            }
        }

        handler = ParameterHandler(mock_vertex, storage_service=None)
        params, _ = handler.process_field_parameters()

        assert params["item"] == "Second item: second"


class TestEndToEndReferenceResolution:
    """End-to-end tests for reference resolution."""

    def test_email_not_matched_as_reference(self):
        """Verify that email addresses are not matched as references."""
        graph = MagicMock()
        graph.get_vertex_by_slug = lambda _slug: None

        text = "Contact: user@domain.com for help"
        result = resolve_references(text, graph)

        # Email should remain unchanged
        assert result == text

    def test_reference_at_start_of_text(self):
        """Test reference at the very beginning of text."""
        output = MagicMock()
        output.value = "VALUE"
        vertex = MagicMock()
        vertex.outputs_map = {"out": output}
        graph = MagicMock()
        graph.get_vertex_by_slug = lambda slug: vertex if slug == "Node" else None

        text = "@Node.out is the answer"
        result = resolve_references(text, graph)

        assert result == "VALUE is the answer"

    def test_reference_at_end_of_text(self):
        """Test reference at the very end of text."""
        output = MagicMock()
        output.value = "VALUE"
        vertex = MagicMock()
        vertex.outputs_map = {"out": output}
        graph = MagicMock()
        graph.get_vertex_by_slug = lambda slug: vertex if slug == "Node" else None

        text = "The answer is @Node.out"
        result = resolve_references(text, graph)

        assert result == "The answer is VALUE"

    def test_reference_alone(self):
        """Test reference as the only content."""
        output = MagicMock()
        output.value = "ONLY_VALUE"
        vertex = MagicMock()
        vertex.outputs_map = {"out": output}
        graph = MagicMock()
        graph.get_vertex_by_slug = lambda slug: vertex if slug == "Node" else None

        text = "@Node.out"
        result = resolve_references(text, graph)

        assert result == "ONLY_VALUE"

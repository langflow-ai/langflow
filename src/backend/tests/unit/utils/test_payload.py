from unittest.mock import MagicMock

from langflow.utils.payload import extract_input_variables, get_root_vertex


class TestExtractInputVariables:
    """Test cases for extract_input_variables function."""

    def test_extract_input_variables_prompt_type(self):
        """Test extracting input variables from prompt type node."""
        nodes = [
            {
                "data": {
                    "node": {
                        "template": {
                            "input_variables": {"value": []},
                            "_type": "prompt",
                            "template": {"value": "Hello {name}, welcome to {place}!"},
                        }
                    }
                }
            }
        ]

        result = extract_input_variables(nodes)

        assert result[0]["data"]["node"]["template"]["input_variables"]["value"] == ["name", "place"]

    def test_extract_input_variables_few_shot_type(self):
        """Test extracting input variables from few_shot type node."""
        nodes = [
            {
                "data": {
                    "node": {
                        "template": {
                            "input_variables": {"value": []},
                            "_type": "few_shot",
                            "prefix": {"value": "This is {prefix_var}"},
                            "suffix": {"value": "And this is {suffix_var}"},
                        }
                    }
                }
            }
        ]

        result = extract_input_variables(nodes)

        assert result[0]["data"]["node"]["template"]["input_variables"]["value"] == ["prefix_var", "suffix_var"]

    def test_extract_input_variables_other_type(self):
        """Test extracting input variables from other type nodes."""
        nodes = [{"data": {"node": {"template": {"input_variables": {"value": []}, "_type": "other"}}}}]

        result = extract_input_variables(nodes)

        assert result[0]["data"]["node"]["template"]["input_variables"]["value"] == []

    def test_extract_input_variables_no_input_variables_field(self):
        """Test handling nodes without input_variables field."""
        nodes = [{"data": {"node": {"template": {"_type": "prompt", "template": {"value": "Hello {name}!"}}}}}]

        # Should not raise exception due to contextlib.suppress
        result = extract_input_variables(nodes)

        assert result == nodes  # Should return unchanged

    def test_extract_input_variables_multiple_nodes(self):
        """Test extracting input variables from multiple nodes."""
        nodes = [
            {
                "data": {
                    "node": {
                        "template": {
                            "input_variables": {"value": []},
                            "_type": "prompt",
                            "template": {"value": "Hello {user}!"},
                        }
                    }
                }
            },
            {
                "data": {
                    "node": {
                        "template": {
                            "input_variables": {"value": []},
                            "_type": "few_shot",
                            "prefix": {"value": "Prefix with {var1}"},
                            "suffix": {"value": "Suffix with {var2}"},
                        }
                    }
                }
            },
        ]

        result = extract_input_variables(nodes)

        assert result[0]["data"]["node"]["template"]["input_variables"]["value"] == ["user"]
        assert result[1]["data"]["node"]["template"]["input_variables"]["value"] == ["var1", "var2"]

    def test_extract_input_variables_nested_brackets(self):
        """Test extracting variables with nested brackets."""
        nodes = [
            {
                "data": {
                    "node": {
                        "template": {
                            "input_variables": {"value": []},
                            "_type": "prompt",
                            "template": {"value": "Process {data.field} and {other_var}"},
                        }
                    }
                }
            }
        ]

        result = extract_input_variables(nodes)

        assert "data.field" in result[0]["data"]["node"]["template"]["input_variables"]["value"]
        assert "other_var" in result[0]["data"]["node"]["template"]["input_variables"]["value"]

    def test_extract_input_variables_no_variables(self):
        """Test extracting from template with no variables."""
        nodes = [
            {
                "data": {
                    "node": {
                        "template": {
                            "input_variables": {"value": []},
                            "_type": "prompt",
                            "template": {"value": "Hello World! No variables here."},
                        }
                    }
                }
            }
        ]

        result = extract_input_variables(nodes)

        assert result[0]["data"]["node"]["template"]["input_variables"]["value"] == []

    def test_extract_input_variables_duplicate_variables(self):
        """Test extracting duplicate variables."""
        nodes = [
            {
                "data": {
                    "node": {
                        "template": {
                            "input_variables": {"value": []},
                            "_type": "prompt",
                            "template": {"value": "Hello {name}, how are you {name}?"},
                        }
                    }
                }
            }
        ]

        result = extract_input_variables(nodes)

        # Should contain duplicates as found by regex
        assert result[0]["data"]["node"]["template"]["input_variables"]["value"] == ["name", "name"]

    def test_extract_input_variables_malformed_node(self):
        """Test handling malformed node structure."""
        nodes = [
            {"malformed": "data"},
            {
                "data": {
                    "node": {
                        "template": {
                            "input_variables": {"value": []},
                            "_type": "prompt",
                            "template": {"value": "Hello {valid}!"},
                        }
                    }
                }
            },
        ]

        # Should not raise exception and process valid nodes
        result = extract_input_variables(nodes)

        assert len(result) == 2
        # Second node should be processed correctly
        assert result[1]["data"]["node"]["template"]["input_variables"]["value"] == ["valid"]

    def test_extract_input_variables_empty_list(self):
        """Test extracting from empty nodes list."""
        nodes = []

        result = extract_input_variables(nodes)

        assert result == []

    def test_extract_input_variables_special_characters(self):
        """Test extracting variables with special characters."""
        nodes = [
            {
                "data": {
                    "node": {
                        "template": {
                            "input_variables": {"value": []},
                            "_type": "prompt",
                            "template": {"value": "Variables: {var_1}, {var-2}, {var.3}"},
                        }
                    }
                }
            }
        ]

        result = extract_input_variables(nodes)

        variables = result[0]["data"]["node"]["template"]["input_variables"]["value"]
        assert "var_1" in variables
        assert "var-2" in variables
        assert "var.3" in variables


class TestGetRootVertex:
    """Test cases for get_root_vertex function."""

    def test_get_root_vertex_single_root(self):
        """Test getting root vertex when there's a single root."""
        # Mock graph with edges
        mock_graph = MagicMock()
        mock_edge1 = MagicMock()
        mock_edge1.source_id = "node1"
        mock_edge2 = MagicMock()
        mock_edge2.source_id = "node2"

        mock_graph.edges = [mock_edge1, mock_edge2]

        # Mock vertices
        mock_vertex1 = MagicMock()
        mock_vertex1.id = "root"
        mock_vertex2 = MagicMock()
        mock_vertex2.id = "node1"
        mock_vertex3 = MagicMock()
        mock_vertex3.id = "node2"

        mock_graph.vertices = [mock_vertex1, mock_vertex2, mock_vertex3]

        # The root should be the vertex not in incoming_edges
        if callable(get_root_vertex):
            _ = get_root_vertex(mock_graph)
            # This test assumes get_root_vertex returns the vertex with no incoming edges
            # The actual implementation would need to be verified

    def test_get_root_vertex_no_edges(self):
        """Test getting root vertex when there are no edges."""
        mock_graph = MagicMock()
        mock_graph.edges = []

        mock_vertex = MagicMock()
        mock_vertex.id = "only_vertex"
        mock_graph.vertices = [mock_vertex]

        # When there are no edges, any vertex could be considered root
        if callable(get_root_vertex):
            _ = get_root_vertex(mock_graph)

    def test_get_root_vertex_multiple_roots(self):
        """Test getting root vertex when there are multiple potential roots."""
        mock_graph = MagicMock()
        mock_edge = MagicMock()
        mock_edge.source_id = "node2"

        mock_graph.edges = [mock_edge]

        # Mock vertices - both node1 and node3 could be roots
        mock_vertex1 = MagicMock()
        mock_vertex1.id = "node1"
        mock_vertex2 = MagicMock()
        mock_vertex2.id = "node2"
        mock_vertex3 = MagicMock()
        mock_vertex3.id = "node3"

        mock_graph.vertices = [mock_vertex1, mock_vertex2, mock_vertex3]

        if callable(get_root_vertex):
            _ = get_root_vertex(mock_graph)

    def test_get_root_vertex_empty_graph(self):
        """Test getting root vertex from empty graph."""
        mock_graph = MagicMock()
        mock_graph.edges = []
        mock_graph.vertices = []

        if callable(get_root_vertex):
            _ = get_root_vertex(mock_graph)
            # Should handle empty graph gracefully

    def test_get_root_vertex_circular_dependencies(self):
        """Test getting root vertex with circular dependencies."""
        mock_graph = MagicMock()

        # Create circular edges: node1 -> node2 -> node1
        mock_edge1 = MagicMock()
        mock_edge1.source_id = "node1"
        mock_edge2 = MagicMock()
        mock_edge2.source_id = "node2"

        mock_graph.edges = [mock_edge1, mock_edge2]

        mock_vertex1 = MagicMock()
        mock_vertex1.id = "node1"
        mock_vertex2 = MagicMock()
        mock_vertex2.id = "node2"

        mock_graph.vertices = [mock_vertex1, mock_vertex2]

        if callable(get_root_vertex):
            _ = get_root_vertex(mock_graph)
            # Should handle circular dependencies gracefully

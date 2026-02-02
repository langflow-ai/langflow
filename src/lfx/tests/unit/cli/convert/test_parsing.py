"""Unit tests for the parsing module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from lfx.cli.convert.parsing import (
    _parse_to_snake_case,
    _parse_unique_var_name,
    _parse_var_name,
    parse_flow_json,
)
from lfx.cli.convert.types import EdgeInfo, FlowInfo, NodeInfo


class TestParseToSnakeCase:
    """Tests for _parse_to_snake_case function."""

    def test_should_convert_camel_case(self) -> None:
        """Test converting CamelCase to snake_case."""
        assert _parse_to_snake_case("CamelCase") == "camel_case"

    def test_should_convert_pascal_case(self) -> None:
        """Test converting PascalCase to snake_case."""
        assert _parse_to_snake_case("PascalCase") == "pascal_case"

    def test_should_handle_spaces(self) -> None:
        """Test converting string with spaces."""
        assert _parse_to_snake_case("Hello World") == "hello_world"

    def test_should_handle_multiple_spaces(self) -> None:
        """Test converting string with multiple spaces."""
        assert _parse_to_snake_case("Hello   World") == "hello_world"

    def test_should_remove_special_characters(self) -> None:
        """Test removing special characters but preserving word boundaries."""
        assert _parse_to_snake_case("Hello@World!") == "hello_world"

    def test_should_handle_empty_string(self) -> None:
        """Test handling empty string."""
        assert _parse_to_snake_case("") == ""

    def test_should_handle_numbers(self) -> None:
        """Test handling strings with numbers."""
        assert _parse_to_snake_case("Model123") == "model123"

    def test_should_collapse_multiple_underscores(self) -> None:
        """Test collapsing multiple underscores."""
        assert _parse_to_snake_case("Hello__World") == "hello_world"


class TestParseVarName:
    """Tests for _parse_var_name function."""

    def test_should_use_display_name_when_provided(self) -> None:
        """Test using display_name for variable name."""
        result = _parse_var_name("Chat Input", "ChatInput")
        assert result == "chat_input"

    def test_should_fallback_to_node_type(self) -> None:
        """Test falling back to node_type when display_name is empty."""
        result = _parse_var_name("", "ChatInput")
        assert result == "chat_input"

    def test_should_prefix_if_starts_with_digit(self) -> None:
        """Test prefixing with 'node_' if name starts with digit."""
        result = _parse_var_name("123Component", "Type")
        assert result.startswith("node_")

    def test_should_handle_reserved_words(self) -> None:
        """Test handling Python reserved words."""
        result = _parse_var_name("input", "InputComponent")
        assert result == "input_component"

    def test_should_handle_class_reserved_word(self) -> None:
        """Test handling 'class' reserved word."""
        result = _parse_var_name("class", "ClassComponent")
        assert result == "class_component"


class TestParseUniqueVarName:
    """Tests for _parse_unique_var_name function."""

    def test_should_return_base_name_when_not_used(self) -> None:
        """Test returning base name when it's not used."""
        used_names: dict[str, int] = {}
        result = _parse_unique_var_name("chat_input", used_names)
        assert result == "chat_input"

    def test_should_append_number_when_name_used(self) -> None:
        """Test appending number when name is already used."""
        used_names = {"chat_input": 1}
        result = _parse_unique_var_name("chat_input", used_names)
        assert result == "chat_input_2"

    def test_should_increment_number_for_multiple_uses(self) -> None:
        """Test incrementing number for multiple uses."""
        used_names = {"chat_input": 2}
        result = _parse_unique_var_name("chat_input", used_names)
        assert result == "chat_input_3"


class TestParseFlowJson:
    """Tests for parse_flow_json function."""

    @pytest.fixture
    def simple_flow_json(self, tmp_path: Path) -> Path:
        """Create a simple flow JSON file for testing."""
        flow_data = {
            "name": "Test Flow",
            "description": "A test flow",
            "data": {
                "nodes": [
                    {
                        "data": {
                            "id": "node-1",
                            "type": "ChatInput",
                            "node": {
                                "display_name": "Chat Input",
                                "template": {
                                    "input_value": {"value": "Hello"},
                                },
                            },
                        },
                    },
                    {
                        "data": {
                            "id": "node-2",
                            "type": "ChatOutput",
                            "node": {
                                "display_name": "Chat Output",
                                "template": {},
                            },
                        },
                    },
                ],
                "edges": [
                    {
                        "source": "node-1",
                        "target": "node-2",
                        "data": {
                            "sourceHandle": {"name": "message_response"},
                            "targetHandle": {"fieldName": "input_value"},
                        },
                    },
                ],
            },
        }
        flow_path = tmp_path / "test_flow.json"
        flow_path.write_text(json.dumps(flow_data))
        return flow_path

    def test_should_parse_flow_name(self, simple_flow_json: Path) -> None:
        """Test parsing flow name from JSON."""
        result = parse_flow_json(simple_flow_json)
        assert result.name == "Test Flow"

    def test_should_parse_flow_description(self, simple_flow_json: Path) -> None:
        """Test parsing flow description from JSON."""
        result = parse_flow_json(simple_flow_json)
        assert result.description == "A test flow"

    def test_should_parse_nodes(self, simple_flow_json: Path) -> None:
        """Test parsing nodes from JSON."""
        result = parse_flow_json(simple_flow_json)
        assert len(result.nodes) == 2

    def test_should_parse_node_ids(self, simple_flow_json: Path) -> None:
        """Test parsing node IDs."""
        result = parse_flow_json(simple_flow_json)
        node_ids = [n.node_id for n in result.nodes]
        assert "node-1" in node_ids
        assert "node-2" in node_ids

    def test_should_parse_node_types(self, simple_flow_json: Path) -> None:
        """Test parsing node types."""
        result = parse_flow_json(simple_flow_json)
        node_types = [n.node_type for n in result.nodes]
        assert "ChatInput" in node_types
        assert "ChatOutput" in node_types

    def test_should_generate_unique_var_names(self, simple_flow_json: Path) -> None:
        """Test generating unique variable names for nodes."""
        result = parse_flow_json(simple_flow_json)
        var_names = [n.var_name for n in result.nodes]
        assert len(var_names) == len(set(var_names))

    def test_should_parse_edges(self, simple_flow_json: Path) -> None:
        """Test parsing edges from JSON."""
        result = parse_flow_json(simple_flow_json)
        assert len(result.edges) == 1

    def test_should_parse_edge_source_and_target(self, simple_flow_json: Path) -> None:
        """Test parsing edge source and target."""
        result = parse_flow_json(simple_flow_json)
        edge = result.edges[0]
        assert edge.source_id == "node-1"
        assert edge.target_id == "node-2"

    def test_should_parse_edge_handles(self, simple_flow_json: Path) -> None:
        """Test parsing edge handle names."""
        result = parse_flow_json(simple_flow_json)
        edge = result.edges[0]
        assert edge.source_output == "message_response"
        assert edge.target_input == "input_value"

    def test_should_parse_node_config(self, simple_flow_json: Path) -> None:
        """Test parsing node configuration values."""
        result = parse_flow_json(simple_flow_json)
        chat_input = next(n for n in result.nodes if n.node_type == "ChatInput")
        assert chat_input.config.get("input_value") == "Hello"

    @pytest.fixture
    def flow_with_duplicate_names(self, tmp_path: Path) -> Path:
        """Create a flow with duplicate component names."""
        flow_data = {
            "name": "Duplicate Names Flow",
            "data": {
                "nodes": [
                    {
                        "data": {
                            "id": "node-1",
                            "type": "URLComponent",
                            "node": {"display_name": "URL", "template": {}},
                        },
                    },
                    {
                        "data": {
                            "id": "node-2",
                            "type": "URLComponent",
                            "node": {"display_name": "URL", "template": {}},
                        },
                    },
                ],
                "edges": [],
            },
        }
        flow_path = tmp_path / "duplicate_names.json"
        flow_path.write_text(json.dumps(flow_data))
        return flow_path

    def test_should_handle_duplicate_display_names(
        self, flow_with_duplicate_names: Path
    ) -> None:
        """Test handling duplicate display names with unique variable names."""
        result = parse_flow_json(flow_with_duplicate_names)
        var_names = [n.var_name for n in result.nodes]
        assert len(var_names) == 2
        assert len(set(var_names)) == 2
        assert "url" in var_names
        assert "url_2" in var_names

    @pytest.fixture
    def flow_with_long_prompt(self, tmp_path: Path) -> Path:
        """Create a flow with a long prompt that should be extracted."""
        long_prompt = "A" * 300
        flow_data = {
            "name": "Long Prompt Flow",
            "data": {
                "nodes": [
                    {
                        "data": {
                            "id": "node-1",
                            "type": "PromptComponent",
                            "node": {
                                "display_name": "Prompt",
                                "template": {
                                    "template": {"value": long_prompt},
                                },
                            },
                        },
                    },
                ],
                "edges": [],
            },
        }
        flow_path = tmp_path / "long_prompt.json"
        flow_path.write_text(json.dumps(flow_data))
        return flow_path

    def test_should_extract_long_prompts(self, flow_with_long_prompt: Path) -> None:
        """Test extracting long prompts into separate constants."""
        result = parse_flow_json(flow_with_long_prompt)
        assert len(result.prompts) == 1
        prompt_key = list(result.prompts.keys())[0]
        assert "TEMPLATE" in prompt_key.upper()

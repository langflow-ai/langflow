"""Unit tests for the convert command module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from lfx.cli.convert.command import convert_flow_to_python

if TYPE_CHECKING:
    from pathlib import Path


class TestConvertFlowToPython:
    """Tests for convert_flow_to_python function."""

    @pytest.fixture
    def minimal_flow_json(self, tmp_path: Path) -> Path:
        """Create a minimal valid flow JSON file."""
        flow_data = {
            "name": "Minimal Flow",
            "data": {
                "nodes": [
                    {
                        "data": {
                            "id": "input-1",
                            "type": "ChatInput",
                            "node": {
                                "display_name": "Input",
                                "template": {},
                            },
                        },
                    },
                ],
                "edges": [],
            },
        }
        flow_path = tmp_path / "minimal.json"
        flow_path.write_text(json.dumps(flow_data))
        return flow_path

    def test_should_convert_minimal_flow(self, minimal_flow_json: Path) -> None:
        """Test converting a minimal flow to Python code."""
        result = convert_flow_to_python(minimal_flow_json)
        assert "def build_minimal_flow_graph(" in result
        assert "ChatInput" in result

    def test_should_return_valid_python_code(self, minimal_flow_json: Path) -> None:
        """Test that generated code is valid Python (can be compiled)."""
        result = convert_flow_to_python(minimal_flow_json)
        compile(result, "<string>", "exec")

    @pytest.fixture
    def complete_flow_json(self, tmp_path: Path) -> Path:
        """Create a complete flow JSON with multiple components."""
        flow_data = {
            "name": "Complete Chat Flow",
            "description": "A complete chat flow with model",
            "data": {
                "nodes": [
                    {
                        "data": {
                            "id": "input-1",
                            "type": "ChatInput",
                            "node": {
                                "display_name": "Chat Input",
                                "template": {},
                            },
                        },
                    },
                    {
                        "data": {
                            "id": "model-1",
                            "type": "OpenAIModel",
                            "node": {
                                "display_name": "OpenAI",
                                "template": {
                                    "model_name": {"value": "gpt-4"},
                                    "temperature": {"value": 0.7},
                                },
                            },
                        },
                    },
                    {
                        "data": {
                            "id": "output-1",
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
                        "source": "input-1",
                        "target": "model-1",
                        "data": {
                            "sourceHandle": {"name": "message_response"},
                            "targetHandle": {"fieldName": "input_value"},
                        },
                    },
                    {
                        "source": "model-1",
                        "target": "output-1",
                        "data": {
                            "sourceHandle": {"name": "text_response"},
                            "targetHandle": {"fieldName": "input_value"},
                        },
                    },
                ],
            },
        }
        flow_path = tmp_path / "complete.json"
        flow_path.write_text(json.dumps(flow_data))
        return flow_path

    def test_should_convert_complete_flow(self, complete_flow_json: Path) -> None:
        """Test converting a complete flow with multiple components."""
        result = convert_flow_to_python(complete_flow_json)
        assert "ChatInput" in result
        assert "OpenAI" in result or "OpenAIModel" in result
        assert "ChatOutput" in result

    def test_should_include_config_values(self, complete_flow_json: Path) -> None:
        """Test including configuration values from nodes."""
        result = convert_flow_to_python(complete_flow_json)
        assert "gpt-4" in result
        assert "0.7" in result

    def test_should_generate_connections(self, complete_flow_json: Path) -> None:
        """Test generating connection code for edges."""
        result = convert_flow_to_python(complete_flow_json)
        assert ".set(" in result
        assert "message_response" in result

    @pytest.fixture
    def flow_with_skip_fields(self, tmp_path: Path) -> Path:
        """Create a flow with fields that should be skipped."""
        flow_data = {
            "name": "Skip Fields Flow",
            "data": {
                "nodes": [
                    {
                        "data": {
                            "id": "input-1",
                            "type": "ChatInput",
                            "node": {
                                "display_name": "Input",
                                "template": {
                                    "input_value": {"value": "test"},
                                    "_type": {"value": "str"},
                                    "show": {"value": True},
                                    "advanced": {"value": False},
                                    "_frontend_node_flow_id": {"value": "abc123"},
                                },
                            },
                        },
                    },
                ],
                "edges": [],
            },
        }
        flow_path = tmp_path / "skip_fields.json"
        flow_path.write_text(json.dumps(flow_data))
        return flow_path

    def test_should_skip_internal_fields(self, flow_with_skip_fields: Path) -> None:
        """Test that internal/UI fields are not included in generated code."""
        result = convert_flow_to_python(flow_with_skip_fields)
        assert "_type=" not in result
        assert "show=" not in result
        assert "advanced=" not in result
        assert "_frontend_node_flow_id=" not in result

    def test_should_include_user_config(self, flow_with_skip_fields: Path) -> None:
        """Test that user configuration is included."""
        result = convert_flow_to_python(flow_with_skip_fields)
        assert "input_value=" in result

    @pytest.fixture
    def invalid_json(self, tmp_path: Path) -> Path:
        """Create an invalid JSON file."""
        flow_path = tmp_path / "invalid.json"
        flow_path.write_text("{ invalid json }")
        return flow_path

    def test_should_raise_on_invalid_json(self, invalid_json: Path) -> None:
        """Test that invalid JSON raises an error."""
        with pytest.raises(json.JSONDecodeError):
            convert_flow_to_python(invalid_json)

    def test_should_raise_on_missing_file(self, tmp_path: Path) -> None:
        """Test that missing file raises an error."""
        missing_path = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            convert_flow_to_python(missing_path)


class TestConvertFlowEdgeCases:
    """Tests for edge cases in flow conversion."""

    @pytest.fixture
    def empty_flow_json(self, tmp_path: Path) -> Path:
        """Create a flow with no nodes."""
        flow_data = {
            "name": "Empty Flow",
            "data": {"nodes": [], "edges": []},
        }
        flow_path = tmp_path / "empty.json"
        flow_path.write_text(json.dumps(flow_data))
        return flow_path

    def test_should_handle_empty_flow(self, empty_flow_json: Path) -> None:
        """Test handling a flow with no nodes."""
        result = convert_flow_to_python(empty_flow_json)
        assert "def build_empty_flow_graph(" in result
        assert "return Graph(None, None)" in result

    @pytest.fixture
    def flow_without_name(self, tmp_path: Path) -> Path:
        """Create a flow without a name."""
        flow_data = {
            "data": {
                "nodes": [
                    {
                        "data": {
                            "id": "input-1",
                            "type": "ChatInput",
                            "node": {"display_name": "Input", "template": {}},
                        },
                    },
                ],
                "edges": [],
            },
        }
        flow_path = tmp_path / "unnamed.json"
        flow_path.write_text(json.dumps(flow_data))
        return flow_path

    def test_should_handle_flow_without_name(self, flow_without_name: Path) -> None:
        """Test handling a flow without a name."""
        result = convert_flow_to_python(flow_without_name)
        assert "build_" in result
        assert "_graph(" in result

    @pytest.fixture
    def flow_with_special_chars(self, tmp_path: Path) -> Path:
        """Create a flow with special characters in name."""
        flow_data = {
            "name": "My Flow #1 (Test) @2024!",
            "data": {
                "nodes": [
                    {
                        "data": {
                            "id": "input-1",
                            "type": "ChatInput",
                            "node": {"display_name": "Input", "template": {}},
                        },
                    },
                ],
                "edges": [],
            },
        }
        flow_path = tmp_path / "special.json"
        flow_path.write_text(json.dumps(flow_data))
        return flow_path

    def test_should_sanitize_flow_name(self, flow_with_special_chars: Path) -> None:
        """Test sanitizing flow name for function name."""
        result = convert_flow_to_python(flow_with_special_chars)
        assert "def build_my_flow_1_test_2024_graph(" in result

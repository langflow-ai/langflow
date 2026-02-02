"""Unit tests for the convert command module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from lfx.cli.convert.command import convert_flow_to_python


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


class TestConvertStarterProjects:
    """Tests using real flows from starter projects.

    These tests ensure the converter works with production flows,
    not just synthetic test data.
    """

    STARTER_PROJECTS_PATH = Path(__file__).parents[6] / (
        "backend/base/langflow/initial_setup/starter_projects"
    )

    # Representative flows to test different component types
    STARTER_FLOWS = [
        "Basic Prompting.json",  # Simple flow with ChatInput, Prompt, OpenAI, ChatOutput
        "Memory Chatbot.json",  # Flow with memory component
        "Simple Agent.json",  # Flow with agent and tools
        "Vector Store RAG.json",  # Flow with vector store and retrieval
    ]

    @pytest.fixture(params=STARTER_FLOWS)
    def starter_flow_path(self, request: pytest.FixtureRequest) -> Path:
        """Parametrized fixture that yields each starter flow path."""
        flow_path = self.STARTER_PROJECTS_PATH / request.param
        if not flow_path.exists():
            pytest.skip(f"Starter project not found: {request.param}")
        return flow_path

    def test_starter_flow_converts_to_valid_python(self, starter_flow_path: Path) -> None:
        """Test that starter flows convert to valid Python code."""
        result = convert_flow_to_python(starter_flow_path)

        # Should compile without syntax errors
        try:
            compile(result, "<string>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}\n\nCode:\n{result[:2000]}...")

    def test_starter_flow_has_required_structure(self, starter_flow_path: Path) -> None:
        """Test that generated code has the required structure."""
        result = convert_flow_to_python(starter_flow_path)

        # Must have essential imports
        assert "from lfx.graph import Graph" in result

        # Must have builder function
        assert "def build_" in result
        assert "_graph(" in result
        assert ") -> Graph:" in result

        # Must have get_graph entry point
        assert "def get_graph() -> Graph:" in result

        # Must have main block
        assert 'if __name__ == "__main__":' in result

    def test_starter_flow_has_components(self, starter_flow_path: Path) -> None:
        """Test that generated code instantiates components."""
        result = convert_flow_to_python(starter_flow_path)

        # Should have at least one component instantiation
        assert "# === Components ===" in result

        # Should have ChatInput or TextInput (most flows have input)
        has_input = "ChatInput(" in result or "TextInput(" in result
        # Some flows might have webhook or other inputs
        has_any_component = "Component(" in result or "(_id=" in result

        assert has_input or has_any_component, "No component instantiation found"

    def test_starter_flow_has_connections(self, starter_flow_path: Path) -> None:
        """Test that generated code has connection setup."""
        result = convert_flow_to_python(starter_flow_path)

        # Should have connections section (most flows have connections)
        assert "# === Connections ===" in result

        # Most flows should have .set() calls (unless single node)
        # Don't fail on this as some minimal flows may not have connections
        if ".set(" not in result:
            # Check if it's a single-node flow (no connections expected)
            import json

            with starter_flow_path.open() as f:
                data = json.load(f)
            flow_data = data.get("data", data)
            edges = flow_data.get("edges", [])
            if edges:
                pytest.fail("Flow has edges but no .set() calls in generated code")

    @pytest.mark.parametrize(
        "flow_name",
        [
            "Basic Prompting.json",
            "Basic Prompt Chaining.json",
        ],
    )
    def test_specific_basic_flows(self, flow_name: str) -> None:
        """Test specific basic flows that should always work."""
        flow_path = self.STARTER_PROJECTS_PATH / flow_name
        if not flow_path.exists():
            pytest.skip(f"Starter project not found: {flow_name}")

        result = convert_flow_to_python(flow_path)

        # Basic flows should have these components
        assert "ChatInput" in result
        assert "ChatOutput" in result

        # Should compile
        compile(result, "<string>", "exec")

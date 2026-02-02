"""Unit tests for the generator module."""

from __future__ import annotations

import pytest
from lfx.cli.convert.generator import generate_python_code
from lfx.cli.convert.types import EdgeInfo, FlowInfo, NodeInfo


class TestGeneratePythonCode:
    """Tests for generate_python_code function."""

    @pytest.fixture
    def simple_flow_info(self) -> FlowInfo:
        """Create a simple FlowInfo for testing."""
        return FlowInfo(
            name="Simple Chat",
            description="A simple chat flow",
            nodes=[
                NodeInfo(
                    node_id="node-1",
                    node_type="ChatInput",
                    display_name="Chat Input",
                    var_name="chat_input",
                    config={},
                ),
                NodeInfo(
                    node_id="node-2",
                    node_type="ChatOutput",
                    display_name="Chat Output",
                    var_name="chat_output",
                    config={},
                ),
            ],
            edges=[
                EdgeInfo(
                    source_id="node-1",
                    source_output="message_response",
                    target_id="node-2",
                    target_input="input_value",
                ),
            ],
        )

    def test_should_generate_module_docstring(self, simple_flow_info: FlowInfo) -> None:
        """Test generating module docstring with flow name."""
        result = generate_python_code(simple_flow_info)
        assert '"""Flow: Simple Chat' in result

    def test_should_include_description_in_docstring(self, simple_flow_info: FlowInfo) -> None:
        """Test including flow description in docstring."""
        result = generate_python_code(simple_flow_info)
        assert "A simple chat flow" in result

    def test_should_include_auto_generated_notice(self, simple_flow_info: FlowInfo) -> None:
        """Test including auto-generated notice."""
        result = generate_python_code(simple_flow_info)
        assert "Auto-generated from JSON" in result

    def test_should_import_graph(self, simple_flow_info: FlowInfo) -> None:
        """Test importing Graph class."""
        result = generate_python_code(simple_flow_info)
        assert "from lfx.graph import Graph" in result

    def test_should_import_components(self, simple_flow_info: FlowInfo) -> None:
        """Test importing component classes."""
        result = generate_python_code(simple_flow_info)
        assert "ChatInput" in result
        assert "ChatOutput" in result

    def test_should_generate_build_function(self, simple_flow_info: FlowInfo) -> None:
        """Test generating build_*_graph function."""
        result = generate_python_code(simple_flow_info)
        assert "def build_simple_chat_graph(" in result

    def test_should_include_function_parameters(self, simple_flow_info: FlowInfo) -> None:
        """Test including function parameters."""
        result = generate_python_code(simple_flow_info)
        assert "provider: str | None = None" in result
        assert "model_name: str | None = None" in result
        assert "api_key: str | None = None" in result

    def test_should_generate_component_instantiation(self, simple_flow_info: FlowInfo) -> None:
        """Test generating component instantiation code."""
        result = generate_python_code(simple_flow_info)
        assert "chat_input = ChatInput(" in result
        assert "chat_output = ChatOutput(" in result

    def test_should_include_node_ids(self, simple_flow_info: FlowInfo) -> None:
        """Test including node IDs in component instantiation."""
        result = generate_python_code(simple_flow_info)
        assert '_id="node-1"' in result
        assert '_id="node-2"' in result

    def test_should_generate_connections(self, simple_flow_info: FlowInfo) -> None:
        """Test generating .set() connection code."""
        result = generate_python_code(simple_flow_info)
        assert ".set(" in result
        assert "input_value=chat_input.message_response" in result

    def test_should_generate_graph_return(self, simple_flow_info: FlowInfo) -> None:
        """Test generating Graph return statement."""
        result = generate_python_code(simple_flow_info)
        assert "return Graph(" in result

    def test_should_identify_start_node(self, simple_flow_info: FlowInfo) -> None:
        """Test identifying ChatInput as start node."""
        result = generate_python_code(simple_flow_info)
        assert "return Graph(chat_input," in result

    def test_should_identify_end_node(self, simple_flow_info: FlowInfo) -> None:
        """Test identifying ChatOutput as end node."""
        result = generate_python_code(simple_flow_info)
        assert "chat_output)" in result

    def test_should_generate_main_block(self, simple_flow_info: FlowInfo) -> None:
        """Test generating if __name__ == '__main__' block."""
        result = generate_python_code(simple_flow_info)
        assert 'if __name__ == "__main__":' in result

    def test_should_generate_get_graph_function(self, simple_flow_info: FlowInfo) -> None:
        """Test generating get_graph() entry point for lfx run compatibility."""
        result = generate_python_code(simple_flow_info)
        assert "def get_graph() -> Graph:" in result
        assert "return build_simple_chat_graph()" in result

    def test_should_include_get_graph_docstring(self, simple_flow_info: FlowInfo) -> None:
        """Test that get_graph() has proper docstring."""
        result = generate_python_code(simple_flow_info)
        assert "Entry point for lfx run command" in result

    @pytest.fixture
    def flow_with_config(self) -> FlowInfo:
        """Create a FlowInfo with component configuration."""
        return FlowInfo(
            name="Configured Flow",
            description="",
            nodes=[
                NodeInfo(
                    node_id="node-1",
                    node_type="OpenAIModel",
                    display_name="OpenAI",
                    var_name="openai_model",
                    config={
                        "model_name": "gpt-4",
                        "temperature": 0.7,
                        "max_tokens": 1000,
                    },
                ),
            ],
            edges=[],
        )

    def test_should_include_config_values(self, flow_with_config: FlowInfo) -> None:
        """Test including configuration values in component instantiation."""
        result = generate_python_code(flow_with_config)
        assert "model_name=" in result
        assert "gpt-4" in result
        assert "temperature=" in result
        assert "0.7" in result

    @pytest.fixture
    def flow_with_prompts(self) -> FlowInfo:
        """Create a FlowInfo with extracted prompts."""
        return FlowInfo(
            name="Prompt Flow",
            description="",
            nodes=[
                NodeInfo(
                    node_id="node-1",
                    node_type="PromptComponent",
                    display_name="Prompt",
                    var_name="prompt",
                    config={"template": "$PROMPT_TEMPLATE"},
                ),
            ],
            edges=[],
            prompts={"PROMPT_TEMPLATE": "You are a helpful assistant."},
        )

    def test_should_generate_prompt_constants(self, flow_with_prompts: FlowInfo) -> None:
        """Test generating prompt constant definitions."""
        result = generate_python_code(flow_with_prompts)
        assert "PROMPT_TEMPLATE = " in result
        assert "You are a helpful assistant." in result

    def test_should_reference_prompt_constant_in_config(self, flow_with_prompts: FlowInfo) -> None:
        """Test referencing prompt constant in component config."""
        result = generate_python_code(flow_with_prompts)
        assert "template=PROMPT_TEMPLATE" in result

    @pytest.fixture
    def flow_with_tools(self) -> FlowInfo:
        """Create a FlowInfo with tool connections."""
        return FlowInfo(
            name="Agent Flow",
            description="",
            nodes=[
                NodeInfo(
                    node_id="tool-1",
                    node_type="Calculator",
                    display_name="Calculator",
                    var_name="calculator",
                    config={},
                ),
                NodeInfo(
                    node_id="agent-1",
                    node_type="Agent",
                    display_name="Agent",
                    var_name="agent",
                    config={},
                ),
            ],
            edges=[
                EdgeInfo(
                    source_id="tool-1",
                    source_output="component_as_tool",
                    target_id="agent-1",
                    target_input="tools",
                ),
            ],
        )

    def test_should_generate_tool_connections(self, flow_with_tools: FlowInfo) -> None:
        """Test generating tool connections using component_as_tool."""
        result = generate_python_code(flow_with_tools)
        assert "tools=[calculator.component_as_tool]" in result

    @pytest.fixture
    def flow_with_custom_code(self) -> FlowInfo:
        """Create a FlowInfo with custom component code."""
        custom_code = """class CustomComponent(Component):
    def build(self):
        return "custom"
"""
        return FlowInfo(
            name="Custom Flow",
            description="",
            nodes=[
                NodeInfo(
                    node_id="custom-1",
                    node_type="CustomComponent",
                    display_name="Custom",
                    var_name="custom",
                    config={},
                    has_custom_code=True,
                    custom_code=custom_code,
                ),
            ],
            edges=[],
        )

    def test_should_include_custom_component_code(self, flow_with_custom_code: FlowInfo) -> None:
        """Test including custom component class definitions."""
        result = generate_python_code(flow_with_custom_code)
        assert "# Custom Components" in result
        assert "class CustomComponent" in result

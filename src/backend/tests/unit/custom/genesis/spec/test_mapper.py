"""Tests for Genesis Spec Mapper."""

import pytest
from unittest.mock import Mock, patch
from langflow.custom.genesis.spec.mapper import ComponentMapper


class TestComponentMapper:
    """Test ComponentMapper class."""

    @pytest.fixture
    def mapper(self):
        """Create ComponentMapper instance."""
        return ComponentMapper()

    def test_mapper_initialization(self, mapper):
        """Test ComponentMapper initialization."""
        assert mapper.AUTONOMIZE_MODELS is not None
        assert mapper.STANDARD_MAPPINGS is not None
        assert mapper.MCP_MAPPINGS is not None

    def test_autonomize_model_mappings(self, mapper):
        """Test AutonomizeModel component mappings."""
        # Test standard RxNorm mapping
        mapping = mapper.map_component("genesis:rxnorm", {})
        assert mapping["component"] == "AutonomizeModel"
        assert mapping["config"]["selected_model"] == "RxNorm Code"

        # Test ICD-10 mapping
        mapping = mapper.map_component("genesis:icd10", {})
        assert mapping["component"] == "AutonomizeModel"
        assert mapping["config"]["selected_model"] == "ICD-10 Code"

        # Test CPT Code mapping
        mapping = mapper.map_component("genesis:cpt_code", {})
        assert mapping["component"] == "AutonomizeModel"
        assert mapping["config"]["selected_model"] == "CPT Code"

        # Test CPT alias
        mapping = mapper.map_component("genesis:cpt", {})
        assert mapping["component"] == "AutonomizeModel"
        assert mapping["config"]["selected_model"] == "CPT Code"

        # Test Clinical LLM
        mapping = mapper.map_component("genesis:clinical_llm", {})
        assert mapping["component"] == "AutonomizeModel"
        assert mapping["config"]["selected_model"] == "Clinical LLM"

        # Test Clinical Note Classifier
        mapping = mapper.map_component("genesis:clinical_note_classifier", {})
        assert mapping["component"] == "AutonomizeModel"
        assert mapping["config"]["selected_model"] == "Clinical Note Classifier"

        # Test Combined Entity Linking
        mapping = mapper.map_component("genesis:combined_entity_linking", {})
        assert mapping["component"] == "AutonomizeModel"
        assert mapping["config"]["selected_model"] == "Combined Entity Linking"

    def test_standard_component_mappings(self, mapper):
        """Test standard component mappings."""
        # Test Agent mapping
        mapping = mapper.map_component("genesis:agent", {})
        assert mapping["component"] == "AgentComponent"
        assert mapping["config"] == {}

        # Test Chat Input
        mapping = mapper.map_component("genesis:chat_input", {})
        assert mapping["component"] == "ChatInput"

        # Test Chat Output
        mapping = mapper.map_component("genesis:chat_output", {})
        assert mapping["component"] == "ChatOutput"

        # Test Prompt
        mapping = mapper.map_component("genesis:prompt", {})
        assert mapping["component"] == "PromptTemplate"

        # Test Calculator
        mapping = mapper.map_component("genesis:calculator", {})
        assert mapping["component"] == "CalculatorTool"

    def test_mcp_component_mappings(self, mapper):
        """Test MCP component mappings."""
        # Test MCP Tool
        mapping = mapper.map_component("genesis:mcp_tool", {})
        assert mapping["component"] == "MCPTool"

        # Test MCP Client
        mapping = mapper.map_component("genesis:mcp_client", {})
        assert mapping["component"] == "MCPClient"

    def test_config_merging(self, mapper):
        """Test that component configs are properly merged."""
        # Test with custom config
        custom_config = {"custom_param": "value", "temperature": 0.7}
        mapping = mapper.map_component("genesis:agent", custom_config)

        assert mapping["component"] == "AgentComponent"
        assert mapping["config"]["custom_param"] == "value"
        assert mapping["config"]["temperature"] == 0.7

        # Test that model configs are merged properly
        mapping = mapper.map_component("genesis:clinical_llm", custom_config)
        assert mapping["component"] == "AutonomizeModel"
        assert mapping["config"]["selected_model"] == "Clinical LLM"
        assert mapping["config"]["custom_param"] == "value"
        assert mapping["config"]["temperature"] == 0.7

    def test_unknown_component_type(self, mapper):
        """Test handling of unknown component types."""
        with pytest.raises(ValueError) as exc_info:
            mapper.map_component("unknown:component", {})

        assert "Unknown component type" in str(exc_info.value)
        assert "unknown:component" in str(exc_info.value)

    def test_get_component_template(self, mapper):
        """Test getting component templates."""
        with patch('langflow.services.spec.component_template_service.component_template_service') as mock_service:
            mock_template = {
                "template": {
                    "input_value": {"type": "str", "required": True},
                    "tools": {"type": "Tool", "list": True}
                },
                "outputs": [
                    {"name": "response", "type": "Message"}
                ]
            }
            mock_service.get_component_template.return_value = mock_template

            template = mapper.get_component_template("AgentComponent")

            assert template == mock_template
            mock_service.get_component_template.assert_called_once_with("AgentComponent")

    def test_get_output_field(self, mapper):
        """Test getting output field for components."""
        # Test ChatInput output
        output_field = mapper.get_output_field("ChatInput")
        assert output_field == "message"

        # Test Agent output
        output_field = mapper.get_output_field("AgentComponent")
        assert output_field == "response"

        # Test ChatOutput output (should be None as it's a sink)
        output_field = mapper.get_output_field("ChatOutput")
        assert output_field is None

        # Test AutonomizeModel output
        output_field = mapper.get_output_field("AutonomizeModel")
        assert output_field == "prediction"

        # Test MCPTool output
        output_field = mapper.get_output_field("MCPTool")
        assert output_field == "component_as_tool"

        # Test unknown component
        output_field = mapper.get_output_field("UnknownComponent")
        assert output_field == "output"  # Default

    def test_get_output_type(self, mapper):
        """Test getting output type for components."""
        # Test Message types
        assert mapper.get_output_type("ChatInput") == ["Message"]
        assert mapper.get_output_type("AgentComponent") == ["Message"]
        assert mapper.get_output_type("PromptTemplate") == ["Message"]

        # Test Data types
        assert mapper.get_output_type("AutonomizeModel") == ["Data"]

        # Test Tool types
        assert mapper.get_output_type("MCPTool") == ["Tool"]
        assert mapper.get_output_type("CalculatorTool") == ["Tool"]

        # Test unknown component
        assert mapper.get_output_type("UnknownComponent") == ["Data"]  # Default

    def test_determine_handle_type(self, mapper):
        """Test handle type determination."""
        # Test single input type
        assert mapper.determine_handle_type(["Message"]) == "str"
        assert mapper.determine_handle_type(["Data"]) == "str"

        # Test multiple input types (should be "other")
        assert mapper.determine_handle_type(["Message", "Data"]) == "other"
        assert mapper.determine_handle_type(["Tool", "Message"]) == "other"

        # Test Tool type (should be "other")
        assert mapper.determine_handle_type(["Tool"]) == "other"

        # Test empty list (should be "str")
        assert mapper.determine_handle_type([]) == "str"

    def test_component_supports_tools(self, mapper):
        """Test checking if component supports tools."""
        # Components that support tools
        assert mapper.component_supports_tools("AgentComponent") is True
        assert mapper.component_supports_tools("MCPClient") is True

        # Components that don't support tools
        assert mapper.component_supports_tools("ChatInput") is False
        assert mapper.component_supports_tools("ChatOutput") is False
        assert mapper.component_supports_tools("PromptTemplate") is False
        assert mapper.component_supports_tools("AutonomizeModel") is False

    def test_is_model_component(self, mapper):
        """Test checking if component is a model component."""
        # Model components
        assert mapper.is_model_component("AutonomizeModel") is True
        assert mapper.is_model_component("OpenAIModel") is True
        assert mapper.is_model_component("AnthropicModel") is True

        # Non-model components
        assert mapper.is_model_component("AgentComponent") is False
        assert mapper.is_model_component("ChatInput") is False
        assert mapper.is_model_component("MCPTool") is False

    def test_get_compatible_types(self, mapper):
        """Test getting compatible types for connections."""
        # Message compatibility
        message_types = mapper.get_compatible_types("Message")
        assert "Message" in message_types
        assert "str" in message_types

        # Data compatibility
        data_types = mapper.get_compatible_types("Data")
        assert "Data" in data_types
        assert "str" in data_types

        # Tool compatibility
        tool_types = mapper.get_compatible_types("Tool")
        assert "Tool" in tool_types

        # Unknown type
        unknown_types = mapper.get_compatible_types("Unknown")
        assert "Unknown" in unknown_types

    def test_component_priority(self, mapper):
        """Test component priority for mapping."""
        # AutonomizeModel variants should have high priority
        assert "genesis:clinical_llm" in mapper.AUTONOMIZE_MODELS

        # Standard mappings should be available
        assert "genesis:agent" in mapper.STANDARD_MAPPINGS

        # MCP mappings should be available
        assert "genesis:mcp_tool" in mapper.MCP_MAPPINGS

    def test_mapping_consistency(self, mapper):
        """Test that all mappings are consistent."""
        # Test all AutonomizeModel mappings
        for component_type in mapper.AUTONOMIZE_MODELS:
            mapping = mapper.map_component(component_type, {})
            assert mapping["component"] == "AutonomizeModel"
            assert "selected_model" in mapping["config"]

        # Test all standard mappings
        for component_type in mapper.STANDARD_MAPPINGS:
            mapping = mapper.map_component(component_type, {})
            assert "component" in mapping
            assert "config" in mapping

        # Test all MCP mappings
        for component_type in mapper.MCP_MAPPINGS:
            mapping = mapper.map_component(component_type, {})
            assert "component" in mapping
            assert "config" in mapping

    def test_edge_case_inputs(self, mapper):
        """Test edge cases and invalid inputs."""
        # Test empty string
        with pytest.raises(ValueError):
            mapper.map_component("", {})

        # Test None input
        with pytest.raises((ValueError, TypeError)):
            mapper.map_component(None, {})

        # Test component type without genesis prefix
        with pytest.raises(ValueError):
            mapper.map_component("agent", {})
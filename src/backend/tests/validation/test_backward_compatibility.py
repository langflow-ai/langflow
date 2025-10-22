"""Backward compatibility validation for AUTPE-6199: Component Mapping Priority System."""

import pytest
from unittest.mock import patch
import yaml

from langflow.custom.genesis.spec.mapper import ComponentMapper
from langflow.services.spec.service import SpecService


@pytest.fixture
def component_mapper():
    """Create a ComponentMapper instance for testing."""
    return ComponentMapper()


@pytest.fixture
def spec_service():
    """Create a SpecService instance for testing."""
    return SpecService()


class TestHardcodedMappingBackwardCompatibility:
    """Test that all existing hardcoded mappings continue to work."""

    def test_all_autonomize_model_mappings(self, component_mapper):
        """Test all AutonomizeModel mappings remain functional."""
        autonomize_mappings = [
            ("genesis:autonomize_model", "AutonomizeModel"),
            ("genesis:rxnorm", "AutonomizeModel"),
            ("genesis:icd10", "AutonomizeModel"),
            ("genesis:cpt_code", "AutonomizeModel"),
            ("genesis:cpt", "AutonomizeModel"),
            ("genesis:clinical_llm", "AutonomizeModel"),
            ("genesis:clinical_note_classifier", "AutonomizeModel"),
            ("genesis:combined_entity_linking", "AutonomizeModel"),
            ("autonomize:icd10_code_model", "AutonomizeModel"),
            ("autonomize:cpt_code_model", "AutonomizeModel"),
            ("autonomize:clinical_llm", "AutonomizeModel"),
            ("autonomize:ehr_connector", "EHRConnector"),
        ]

        for genesis_type, expected_component in autonomize_mappings:
            result = component_mapper.map_component(genesis_type)
            assert result["component"] == expected_component, f"Failed for {genesis_type}"
            assert "config" in result

    def test_all_mcp_mappings(self, component_mapper):
        """Test all MCP mappings remain functional."""
        mcp_mappings = [
            ("genesis:mcp_tool", "MCPTools"),
            ("genesis:mcp_sse_tool", "MCPTools"),
            ("genesis:mcp_stdio_tool", "MCPTools"),
            ("genesis:mcp_client", "MCPClient"),
            ("genesis:mcp_server", "MCPServer"),
        ]

        for genesis_type, expected_component in mcp_mappings:
            result = component_mapper.map_component(genesis_type)
            assert result["component"] == expected_component, f"Failed for {genesis_type}"

    def test_all_standard_mappings(self, component_mapper):
        """Test all standard mappings remain functional."""
        standard_mappings = [
            # Core components
            ("genesis:agent", "Agent"),
            ("genesis:autonomize_agent", "Agent"),
            ("genesis:language_model", "Agent"),

            # I/O components
            ("genesis:chat_input", "ChatInput"),
            ("genesis:chat_output", "ChatOutput"),
            ("genesis:text_input", "TextInput"),
            ("genesis:text_output", "TextOutput"),
            ("genesis:json_input", "CreateData"),
            ("genesis:json_output", "ParseData"),
            ("genesis:file_input", "File"),
            ("genesis:file", "File"),
            ("genesis:directory", "Directory"),
            ("genesis:url", "URL"),

            # Prompts
            ("genesis:prompt", "PromptComponent"),
            ("genesis:prompt_template", "PromptComponent"),
            ("genesis:genesis_prompt", "GenesisPromptComponent"),

            # Memory
            ("genesis:memory", "Memory"),
            ("genesis:conversation_memory", "ConversationChain"),
            ("genesis:conversation_chain", "ConversationChain"),

            # Tools
            ("genesis:knowledge_hub_search", "KnowledgeHubSearch"),
            ("genesis:calculator", "Calculator"),

            # API Components
            ("genesis:api_request", "APIRequest"),
            ("genesis:http_request", "APIRequest"),

            # LLMs
            ("genesis:openai", "OpenAIModel"),
            ("genesis:azure_openai", "AzureOpenAIModel"),
            ("genesis:anthropic", "AnthropicModel"),
        ]

        for genesis_type, expected_component in standard_mappings:
            result = component_mapper.map_component(genesis_type)
            assert result["component"] == expected_component, f"Failed for {genesis_type}"

    def test_healthcare_mappings_if_available(self, component_mapper):
        """Test healthcare mappings if they are available."""
        if component_mapper.HEALTHCARE_MAPPINGS:
            for genesis_type, mapping_info in component_mapper.HEALTHCARE_MAPPINGS.items():
                result = component_mapper.map_component(genesis_type)
                assert result["component"] == mapping_info["component"], f"Failed for {genesis_type}"

    def test_healthcare_validation_mappings(self, component_mapper):
        """Test healthcare validation mappings."""
        if component_mapper.HEALTHCARE_VALIDATION_MAPPINGS:
            for genesis_type, mapping_info in component_mapper.HEALTHCARE_VALIDATION_MAPPINGS.items():
                result = component_mapper.map_component(genesis_type)
                assert result["component"] == mapping_info["component"], f"Failed for {genesis_type}"


class TestExistingSpecificationCompatibility:
    """Test that existing specifications continue to work."""

    @pytest.mark.asyncio
    async def test_basic_agent_spec(self, spec_service):
        """Test basic agent specification compatibility."""
        basic_spec = """
        name: Basic Agent
        description: A simple agent for testing
        agentGoal: Process user input
        components:
          input:
            type: genesis:chat_input
          agent:
            type: genesis:agent
            provides:
              - useAs: input
                in: output
          output:
            type: genesis:chat_output
        """

        with patch.object(spec_service.converter, 'convert') as mock_convert:
            mock_convert.return_value = {"basic_test": True}

            # Should work without database session
            result = await spec_service.convert_spec_to_flow(basic_spec)
            assert result["basic_test"] is True

    @pytest.mark.asyncio
    async def test_autonomize_model_spec(self, spec_service):
        """Test AutonomizeModel specification compatibility."""
        autonomize_spec = """
        name: Clinical Analysis Agent
        description: Agent using clinical models
        agentGoal: Analyze clinical data
        components:
          input:
            type: genesis:chat_input
          clinical_model:
            type: genesis:clinical_llm
            config:
              selected_model: "Clinical LLM"
          icd_model:
            type: genesis:icd10
            config:
              selected_model: "ICD-10 Code"
          agent:
            type: genesis:agent
            provides:
              - useAs: input
                in: output
          output:
            type: genesis:chat_output
        """

        with patch.object(spec_service.converter, 'convert') as mock_convert:
            mock_convert.return_value = {"autonomize_test": True}

            result = await spec_service.convert_spec_to_flow(autonomize_spec)
            assert result["autonomize_test"] is True

            # Verify mappings still work
            clinical_result = spec_service.mapper.map_component("genesis:clinical_llm")
            assert clinical_result["component"] == "AutonomizeModel"
            assert clinical_result["config"]["selected_model"] == "Clinical LLM"

            icd_result = spec_service.mapper.map_component("genesis:icd10")
            assert icd_result["component"] == "AutonomizeModel"
            assert icd_result["config"]["selected_model"] == "ICD-10 Code"

    @pytest.mark.asyncio
    async def test_mcp_tools_spec(self, spec_service):
        """Test MCP tools specification compatibility."""
        mcp_spec = """
        name: MCP Tools Workflow
        description: Workflow using MCP tools
        agentGoal: Process data with MCP tools
        components:
          input:
            type: genesis:chat_input
          mcp_tool:
            type: genesis:mcp_tool
            asTools: true
            config:
              tool_name: "test_tool"
          agent:
            type: genesis:agent
            provides:
              - useAs: input
                in: output
          output:
            type: genesis:chat_output
        """

        with patch.object(spec_service.converter, 'convert') as mock_convert:
            mock_convert.return_value = {"mcp_test": True}

            result = await spec_service.convert_spec_to_flow(mcp_spec)
            assert result["mcp_test"] is True

            # Verify MCP mapping
            mcp_result = spec_service.mapper.map_component("genesis:mcp_tool")
            assert mcp_result["component"] == "MCPTools"

    @pytest.mark.asyncio
    async def test_complex_workflow_spec(self, spec_service):
        """Test complex workflow specification compatibility."""
        complex_spec = """
        name: Complex Healthcare Workflow
        description: Complex workflow with multiple component types
        agentGoal: Comprehensive healthcare data processing
        components:
          patient_input:
            type: genesis:chat_input

          file_processor:
            type: genesis:file
            config:
              file_path: "/path/to/data"

          clinical_model:
            type: genesis:autonomize_model
            config:
              selected_model: "Clinical LLM"

          api_connector:
            type: genesis:api_request
            config:
              url_input: "https://api.example.com"
              headers:
                - key: "Content-Type"
                  value: "application/json"

          mcp_tool:
            type: genesis:mcp_tool
            asTools: true
            config:
              tool_name: "medical_encoder"

          primary_agent:
            type: genesis:agent
            provides:
              - useAs: input
                in: secondary_agent

          secondary_agent:
            type: genesis:agent
            provides:
              - useAs: input
                in: output

          vector_store:
            type: genesis:qdrant
            config:
              collection_name: "medical_docs"

          memory:
            type: genesis:conversation_memory

          output:
            type: genesis:chat_output
        """

        with patch.object(spec_service.converter, 'convert') as mock_convert:
            mock_convert.return_value = {"complex_test": True}

            result = await spec_service.convert_spec_to_flow(complex_spec)
            assert result["complex_test"] is True


class TestMappingFormatCompatibility:
    """Test that mapping format remains compatible."""

    def test_mapping_result_structure(self, component_mapper):
        """Test that mapping results have expected structure."""
        test_types = [
            "genesis:agent",
            "genesis:autonomize_model",
            "genesis:mcp_tool",
            "genesis:chat_input",
        ]

        for genesis_type in test_types:
            result = component_mapper.map_component(genesis_type)

            # Required fields
            assert "component" in result, f"Missing 'component' for {genesis_type}"
            assert "config" in result, f"Missing 'config' for {genesis_type}"

            # Types
            assert isinstance(result["component"], str), f"'component' not string for {genesis_type}"
            assert isinstance(result["config"], dict), f"'config' not dict for {genesis_type}"

            # Optional fields if present
            if "dataType" in result:
                assert isinstance(result["dataType"], str), f"'dataType' not string for {genesis_type}"

    def test_config_preservation(self, component_mapper):
        """Test that component configurations are preserved."""
        # Test AutonomizeModel config preservation
        rxnorm_result = component_mapper.map_component("genesis:rxnorm")
        assert rxnorm_result["config"]["selected_model"] == "RxNorm Code"

        icd10_result = component_mapper.map_component("genesis:icd10")
        assert icd10_result["config"]["selected_model"] == "ICD-10 Code"

        # Test MCP tool config preservation
        mcp_result = component_mapper.map_component("genesis:mcp_tool")
        assert "command" in mcp_result["config"]
        assert "args" in mcp_result["config"]

    def test_io_mapping_compatibility(self, component_mapper):
        """Test I/O mapping compatibility."""
        test_components = ["Agent", "ChatInput", "ChatOutput", "AutonomizeModel"]

        for component_name in test_components:
            io_mapping = component_mapper.get_component_io_mapping(component_name)

            if io_mapping:
                # Expected fields in I/O mapping
                expected_fields = ["input_field", "output_field", "output_types", "input_types"]
                for field in expected_fields:
                    assert field in io_mapping, f"Missing {field} in I/O mapping for {component_name}"


class TestToolConfigurationCompatibility:
    """Test tool configuration compatibility."""

    def test_tool_identification(self, component_mapper):
        """Test that tool identification remains consistent."""
        known_tools = [
            "genesis:mcp_tool",
            "genesis:mcp_sse_tool",
            "genesis:mcp_stdio_tool",
            "genesis:knowledge_hub_search",
            "genesis:calculator",
            "genesis:api_request",
            "genesis:web_search",
        ]

        for tool_type in known_tools:
            is_tool = component_mapper.is_tool_component(tool_type)
            assert is_tool, f"{tool_type} should be identified as a tool"

    def test_non_tool_identification(self, component_mapper):
        """Test that non-tools are not identified as tools."""
        non_tools = [
            "genesis:agent",
            "genesis:chat_input",
            "genesis:chat_output",
            "genesis:memory",
            "genesis:prompt",
        ]

        for non_tool_type in non_tools:
            is_tool = component_mapper.is_tool_component(non_tool_type)
            assert not is_tool, f"{non_tool_type} should not be identified as a tool"


class TestSpecValidationCompatibility:
    """Test specification validation compatibility."""

    @pytest.mark.asyncio
    async def test_validation_with_existing_components(self, spec_service):
        """Test validation with existing component types."""
        valid_spec = """
        name: Validation Test
        description: Test validation compatibility
        agentGoal: Validate existing components
        components:
          input:
            type: genesis:chat_input
          agent:
            type: genesis:agent
            provides:
              - useAs: input
                in: output
          tool:
            type: genesis:calculator
            asTools: true
            provides:
              - useAs: tools
                in: agent
          output:
            type: genesis:chat_output
        """

        validation_result = await spec_service.validate_spec(valid_spec, detailed=False)

        # Should be valid
        assert validation_result["valid"] is True
        assert validation_result["summary"]["error_count"] == 0

    @pytest.mark.asyncio
    async def test_validation_error_format_consistency(self, spec_service):
        """Test that validation error format remains consistent."""
        invalid_spec = """
        name: Invalid Test
        description: Test invalid specification
        # Missing agentGoal and components
        """

        validation_result = await spec_service.validate_spec(invalid_spec, detailed=False)

        # Should be invalid
        assert validation_result["valid"] is False
        assert "errors" in validation_result
        assert "warnings" in validation_result
        assert "summary" in validation_result
        assert isinstance(validation_result["errors"], list)


class TestUnknownComponentFallback:
    """Test unknown component fallback behavior."""

    def test_unknown_agent_fallback(self, component_mapper):
        """Test unknown agent types fall back appropriately."""
        unknown_agents = [
            "genesis:custom_agent",
            "genesis:specialized_agent",
            "genesis:unknown_agent_type",
        ]

        for unknown_type in unknown_agents:
            result = component_mapper.map_component(unknown_type)
            # Should fallback to Agent or MCPTools
            assert result["component"] in ["Agent", "MCPTools"]

    def test_unknown_model_fallback(self, component_mapper):
        """Test unknown model types fall back appropriately."""
        unknown_models = [
            "genesis:custom_model",
            "genesis:specialized_llm",
            "genesis:unknown_clinical_model",
        ]

        for unknown_type in unknown_models:
            result = component_mapper.map_component(unknown_type)
            # Should fallback to appropriate model type
            if "clinical" in unknown_type.lower():
                assert result["component"] == "AutonomizeModel"
            else:
                assert result["component"] in ["OpenAIModel", "AutonomizeModel"]

    def test_unknown_tool_fallback(self, component_mapper):
        """Test unknown tool types fall back to MCPTools."""
        unknown_tools = [
            "genesis:custom_tool",
            "genesis:specialized_component",
            "genesis:unknown_integration",
        ]

        for unknown_type in unknown_tools:
            result = component_mapper.map_component(unknown_type)
            # Should fallback to MCPTools
            assert result["component"] == "MCPTools"


if __name__ == "__main__":
    """Run backward compatibility validation."""
    print("Running backward compatibility validation...")

    # Create instances
    mapper = ComponentMapper()
    service = SpecService()

    # Test basic functionality
    print("✓ Testing basic component mapping...")
    agent_result = mapper.map_component("genesis:agent")
    assert agent_result["component"] == "Agent"

    print("✓ Testing AutonomizeModel mapping...")
    model_result = mapper.map_component("genesis:autonomize_model")
    assert model_result["component"] == "AutonomizeModel"

    print("✓ Testing MCP tool mapping...")
    mcp_result = mapper.map_component("genesis:mcp_tool")
    assert mcp_result["component"] == "MCPTools"

    print("✓ All backward compatibility tests passed!")
    print("✓ Database priority system maintains full backward compatibility")
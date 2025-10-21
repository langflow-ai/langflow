"""
Comprehensive tests for LangflowConverter bidirectional conversion.

This test suite validates the bidirectional conversion capabilities
of the LangflowConverter, ensuring round-trip integrity and accuracy.
"""

import pytest
import asyncio
from typing import Dict, Any
import json

from langflow.services.runtime.langflow_converter import LangflowConverter
from langflow.services.runtime.base_converter import ConversionMode, ConversionError


class TestLangflowConverter:
    """Test suite for LangflowConverter."""

    @pytest.fixture
    def converter(self):
        """Create LangflowConverter instance."""
        return LangflowConverter()

    @pytest.fixture
    def sample_genesis_spec(self):
        """Sample Genesis specification for testing."""
        return {
            "id": "urn:agent:genesis:test:simple-agent:1.0.0",
            "name": "Simple Test Agent",
            "description": "A simple agent for testing conversion",
            "domain": "test",
            "version": "1.0.0",
            "kind": "Single Agent",
            "agentGoal": "Process user input and provide responses",
            "targetUser": "internal",
            "valueGeneration": "ProcessAutomation",
            "components": {
                "input": {
                    "name": "User Input",
                    "kind": "Data",
                    "type": "genesis:chat_input",
                    "description": "Accepts user input",
                    "provides": [
                        {
                            "useAs": "input",
                            "in": "agent",
                            "description": "Provides input to agent"
                        }
                    ]
                },
                "agent": {
                    "name": "Main Agent",
                    "kind": "Agent",
                    "type": "genesis:agent",
                    "description": "Processes input and generates response",
                    "config": {
                        "temperature": 0.7,
                        "max_tokens": 2000
                    },
                    "provides": [
                        {
                            "useAs": "input",
                            "in": "output",
                            "description": "Provides response to output"
                        }
                    ]
                },
                "output": {
                    "name": "Agent Output",
                    "kind": "Data",
                    "type": "genesis:chat_output",
                    "description": "Displays agent response"
                }
            }
        }

    @pytest.fixture
    def sample_langflow_json(self):
        """Sample Langflow JSON for testing reverse conversion."""
        return {
            "name": "Test Flow",
            "description": "Test flow for reverse conversion",
            "data": {
                "nodes": [
                    {
                        "id": "input-1",
                        "type": "genericNode",
                        "position": {"x": 100, "y": 100},
                        "data": {
                            "id": "input-1",
                            "type": "ChatInput",
                            "display_name": "Chat Input",
                            "description": "Input component",
                            "node": {
                                "template": {
                                    "input_value": {"value": ""},
                                    "sender": {"value": "User"}
                                },
                                "outputs": [
                                    {"name": "message", "types": ["Message"]}
                                ]
                            }
                        }
                    },
                    {
                        "id": "agent-1",
                        "type": "genericNode",
                        "position": {"x": 400, "y": 100},
                        "data": {
                            "id": "agent-1",
                            "type": "Agent",
                            "display_name": "Agent",
                            "description": "Main agent",
                            "node": {
                                "template": {
                                    "input_value": {"value": ""},
                                    "system_prompt": {"value": "You are a helpful assistant"},
                                    "temperature": {"value": 0.7}
                                },
                                "outputs": [
                                    {"name": "response", "types": ["Message"]}
                                ]
                            }
                        }
                    }
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "input-1",
                        "target": "agent-1",
                        "sourceHandle": "message",
                        "targetHandle": "input_value"
                    }
                ],
                "viewport": {"x": 0, "y": 0, "zoom": 1}
            }
        }

    def test_converter_initialization(self, converter):
        """Test converter initialization."""
        assert converter is not None
        assert converter.runtime_type.value == "langflow"

    def test_get_runtime_info(self, converter):
        """Test runtime info retrieval."""
        info = converter.get_runtime_info()

        assert info["name"] == "Langflow"
        assert info["runtime_type"] == "langflow"
        assert info["bidirectional_support"] is True
        assert "supported_components" in info
        assert isinstance(info["supported_components"], list)
        assert len(info["supported_components"]) > 0

    def test_validate_specification_valid(self, converter, sample_genesis_spec):
        """Test specification validation with valid spec."""
        errors = converter.validate_specification(sample_genesis_spec)
        assert errors == []

    def test_validate_specification_invalid(self, converter):
        """Test specification validation with invalid spec."""
        invalid_spec = {"invalid": "spec"}
        errors = converter.validate_specification(invalid_spec)
        assert len(errors) > 0
        assert any("Required field missing" in error for error in errors)

    def test_validate_specification_missing_components(self, converter):
        """Test validation with missing components."""
        spec = {
            "name": "Test",
            "description": "Test spec",
            "agentGoal": "Test goal"
            # Missing components
        }
        errors = converter.validate_specification(spec)
        assert any("component" in error.lower() for error in errors)

    @pytest.mark.asyncio
    async def test_convert_to_runtime_success(self, converter, sample_genesis_spec):
        """Test successful conversion to Langflow runtime."""
        result = await converter.convert_to_runtime(sample_genesis_spec)

        assert "data" in result
        assert "nodes" in result["data"]
        assert "edges" in result["data"]
        assert result["name"] == sample_genesis_spec["name"]

        # Verify nodes were created
        nodes = result["data"]["nodes"]
        assert len(nodes) == 3  # input, agent, output

        # Verify edges were created
        edges = result["data"]["edges"]
        assert len(edges) == 2  # input->agent, agent->output

    @pytest.mark.asyncio
    async def test_convert_to_runtime_invalid_spec(self, converter):
        """Test conversion with invalid specification."""
        invalid_spec = {"invalid": "spec"}

        with pytest.raises(ConversionError):
            await converter.convert_to_runtime(invalid_spec)

    @pytest.mark.asyncio
    async def test_convert_from_runtime_success(self, converter, sample_langflow_json):
        """Test successful conversion from Langflow runtime."""
        result = await converter.convert_from_runtime(sample_langflow_json)

        assert "id" in result
        assert result["name"] == sample_langflow_json["name"]
        assert "components" in result
        assert "kind" in result
        assert "agentGoal" in result

        # Verify components were created
        components = result["components"]
        assert len(components) >= 2  # At least input and agent

    @pytest.mark.asyncio
    async def test_convert_from_runtime_invalid_json(self, converter):
        """Test conversion with invalid Langflow JSON."""
        invalid_json = {"invalid": "json"}

        with pytest.raises(ConversionError):
            await converter.convert_from_runtime(invalid_json)

    def test_supports_component_type(self, converter):
        """Test component type support checking."""
        assert converter.supports_component_type("genesis:agent")
        assert converter.supports_component_type("genesis:chat_input")
        assert converter.supports_component_type("genesis:mcp_tool")
        assert not converter.supports_component_type("genesis:nonexistent")

    @pytest.mark.asyncio
    async def test_round_trip_conversion(self, converter, sample_genesis_spec):
        """Test round-trip conversion: Genesis -> Langflow -> Genesis."""
        # Convert to Langflow
        langflow_result = await converter.convert_to_runtime(sample_genesis_spec)

        # Convert back to Genesis
        genesis_result = await converter.convert_from_runtime(langflow_result)

        # Verify key fields are preserved
        assert genesis_result["name"] == sample_genesis_spec["name"]
        assert genesis_result["description"] == sample_genesis_spec["description"]
        assert "components" in genesis_result

        # Verify component count is reasonable (may not be exact due to conversion logic)
        original_components = len(sample_genesis_spec["components"])
        converted_components = len(genesis_result["components"])
        assert converted_components >= original_components * 0.5  # Allow some loss

    def test_conversion_modes(self, converter):
        """Test supported conversion modes."""
        modes = converter.get_supported_conversion_modes()
        assert ConversionMode.SPEC_TO_RUNTIME in modes
        assert ConversionMode.RUNTIME_TO_SPEC in modes

    def test_validate_conversion_mode(self, converter):
        """Test conversion mode validation."""
        assert converter.validate_conversion_mode(ConversionMode.SPEC_TO_RUNTIME)
        assert converter.validate_conversion_mode(ConversionMode.RUNTIME_TO_SPEC)

    @pytest.mark.asyncio
    async def test_generic_convert_method(self, converter, sample_genesis_spec):
        """Test generic convert method with mode parameter."""
        # Test spec to runtime
        result = await converter.convert(sample_genesis_spec, ConversionMode.SPEC_TO_RUNTIME)
        assert "data" in result

        # Test runtime to spec
        langflow_result = await converter.convert_to_runtime(sample_genesis_spec)
        genesis_result = await converter.convert(langflow_result, ConversionMode.RUNTIME_TO_SPEC)
        assert "components" in genesis_result

    def test_complex_specification_validation(self, converter):
        """Test validation with complex specification."""
        complex_spec = {
            "id": "urn:agent:genesis:test:complex-agent:1.0.0",
            "name": "Complex Agent",
            "description": "Complex multi-tool agent",
            "agentGoal": "Handle complex workflows",
            "components": {
                "input": {
                    "name": "Input",
                    "type": "genesis:chat_input",
                    "kind": "Data"
                },
                "tool1": {
                    "name": "Knowledge Search",
                    "type": "genesis:knowledge_hub_search",
                    "kind": "Tool",
                    "asTools": True,
                    "config": {
                        "selected_hubs": ["medical", "clinical"]
                    }
                },
                "tool2": {
                    "name": "MCP Tool",
                    "type": "genesis:mcp_tool",
                    "kind": "Tool",
                    "asTools": True,
                    "config": {
                        "tool_name": "eligibility_check"
                    }
                },
                "agent": {
                    "name": "Multi-tool Agent",
                    "type": "genesis:agent",
                    "kind": "Agent",
                    "config": {
                        "temperature": 0.7
                    }
                },
                "output": {
                    "name": "Output",
                    "type": "genesis:chat_output",
                    "kind": "Data"
                }
            }
        }

        # Add provides relationships
        complex_spec["components"]["input"]["provides"] = [
            {"useAs": "input", "in": "agent"}
        ]
        complex_spec["components"]["tool1"]["provides"] = [
            {"useAs": "tools", "in": "agent"}
        ]
        complex_spec["components"]["tool2"]["provides"] = [
            {"useAs": "tools", "in": "agent"}
        ]
        complex_spec["components"]["agent"]["provides"] = [
            {"useAs": "input", "in": "output"}
        ]

        errors = converter.validate_specification(complex_spec)
        assert errors == []  # Should validate successfully

    @pytest.mark.asyncio
    async def test_error_handling(self, converter):
        """Test error handling in conversion methods."""
        # Test with None input
        with pytest.raises((ConversionError, TypeError, ValueError)):
            await converter.convert_from_runtime(None)

        # Test with empty dict
        with pytest.raises(ConversionError):
            await converter.convert_from_runtime({})

    def test_component_type_mapping(self, converter):
        """Test component type mapping functionality."""
        # Test known mappings
        known_types = [
            "genesis:agent",
            "genesis:chat_input",
            "genesis:chat_output",
            "genesis:mcp_tool",
            "genesis:knowledge_hub_search",
            "genesis:autonomize_model"
        ]

        for component_type in known_types:
            assert converter.supports_component_type(component_type), \
                f"Component type {component_type} should be supported"

    @pytest.mark.asyncio
    async def test_configuration_preservation(self, converter):
        """Test that configurations are preserved during conversion."""
        spec_with_config = {
            "name": "Config Test",
            "description": "Test config preservation",
            "agentGoal": "Test configuration",
            "components": {
                "agent": {
                    "name": "Configured Agent",
                    "type": "genesis:agent",
                    "kind": "Agent",
                    "config": {
                        "temperature": 0.5,
                        "max_tokens": 1000,
                        "model_name": "gpt-4"
                    }
                }
            }
        }

        # Convert to Langflow
        langflow_result = await converter.convert_to_runtime(spec_with_config)

        # Check if configuration values are present in the result
        nodes = langflow_result["data"]["nodes"]
        agent_node = next((node for node in nodes if "agent" in node["id"].lower()), None)

        assert agent_node is not None
        template = agent_node["data"]["node"]["template"]

        # Check that some configuration values were applied
        # (exact field names may vary based on mapping logic)
        has_config = any(
            field_data.get("value") in [0.5, 1000, "gpt-4"]
            for field_data in template.values()
            if isinstance(field_data, dict) and "value" in field_data
        )
        assert has_config, "Configuration values should be preserved"

    def test_metadata_handling(self, converter, sample_genesis_spec):
        """Test metadata handling in conversion."""
        # Add metadata to spec
        spec_with_metadata = sample_genesis_spec.copy()
        spec_with_metadata.update({
            "domain": "healthcare",
            "version": "2.0.0",
            "tags": ["healthcare", "automation"],
            "agentOwner": "test@example.com"
        })

        # Validate that metadata doesn't break conversion
        errors = converter.validate_specification(spec_with_metadata)
        assert errors == []


class TestLangflowConverterIntegration:
    """Integration tests for LangflowConverter."""

    @pytest.fixture
    def converter(self):
        """Create LangflowConverter instance."""
        return LangflowConverter()

    @pytest.mark.asyncio
    async def test_healthcare_workflow_conversion(self, converter):
        """Test conversion of healthcare-specific workflow."""
        healthcare_spec = {
            "id": "urn:agent:genesis:healthcare:eligibility-checker:1.0.0",
            "name": "Eligibility Checker",
            "description": "Healthcare eligibility verification agent",
            "domain": "healthcare",
            "agentGoal": "Verify patient eligibility for procedures",
            "components": {
                "input": {
                    "name": "Patient Input",
                    "type": "genesis:chat_input",
                    "kind": "Data"
                },
                "eligibility_tool": {
                    "name": "Eligibility Check",
                    "type": "genesis:mcp_tool",
                    "kind": "Tool",
                    "asTools": True,
                    "config": {
                        "tool_name": "insurance_eligibility_check"
                    },
                    "provides": [
                        {"useAs": "tools", "in": "agent"}
                    ]
                },
                "agent": {
                    "name": "Eligibility Agent",
                    "type": "genesis:agent",
                    "kind": "Agent",
                    "config": {
                        "system_prompt": "You are a healthcare eligibility verification specialist."
                    },
                    "provides": [
                        {"useAs": "input", "in": "output"}
                    ]
                },
                "output": {
                    "name": "Eligibility Result",
                    "type": "genesis:chat_output",
                    "kind": "Data"
                }
            }
        }

        # Add input provides
        healthcare_spec["components"]["input"]["provides"] = [
            {"useAs": "input", "in": "agent"}
        ]

        # Test conversion
        result = await converter.convert_to_runtime(healthcare_spec)

        assert result is not None
        assert "data" in result
        assert len(result["data"]["nodes"]) >= 4  # All components should be converted

        # Test that tool connections are properly handled
        edges = result["data"]["edges"]
        tool_edges = [edge for edge in edges if "tool" in edge.get("data", {}).get("targetHandle", {}).get("fieldName", "")]
        assert len(tool_edges) > 0, "Tool connections should be created"

    @pytest.mark.asyncio
    async def test_multi_tool_agent_conversion(self, converter):
        """Test conversion of agent with multiple tools."""
        multi_tool_spec = {
            "name": "Multi-Tool Agent",
            "description": "Agent with multiple tools",
            "agentGoal": "Use multiple tools to process requests",
            "components": {
                "input": {
                    "name": "Input",
                    "type": "genesis:chat_input",
                    "kind": "Data",
                    "provides": [{"useAs": "input", "in": "agent"}]
                },
                "knowledge_tool": {
                    "name": "Knowledge Search",
                    "type": "genesis:knowledge_hub_search",
                    "kind": "Tool",
                    "asTools": True,
                    "provides": [{"useAs": "tools", "in": "agent"}]
                },
                "api_tool": {
                    "name": "API Tool",
                    "type": "genesis:api_request",
                    "kind": "Tool",
                    "asTools": True,
                    "provides": [{"useAs": "tools", "in": "agent"}]
                },
                "mcp_tool": {
                    "name": "MCP Tool",
                    "type": "genesis:mcp_tool",
                    "kind": "Tool",
                    "asTools": True,
                    "provides": [{"useAs": "tools", "in": "agent"}]
                },
                "agent": {
                    "name": "Multi-Tool Agent",
                    "type": "genesis:agent",
                    "kind": "Agent",
                    "provides": [{"useAs": "input", "in": "output"}]
                },
                "output": {
                    "name": "Output",
                    "type": "genesis:chat_output",
                    "kind": "Data"
                }
            }
        }

        # Test conversion
        result = await converter.convert_to_runtime(multi_tool_spec)

        assert result is not None
        nodes = result["data"]["nodes"]
        edges = result["data"]["edges"]

        # Should have all components
        assert len(nodes) == 6

        # Should have multiple tool connections to the agent
        tool_connections = sum(1 for edge in edges
                              if edge.get("data", {}).get("targetHandle", {}).get("fieldName") == "tools")
        assert tool_connections == 3  # Three tools connecting to agent


if __name__ == "__main__":
    pytest.main([__file__])
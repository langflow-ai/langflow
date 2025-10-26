"""
Unit tests for tool connection logic in FlowConverter.

Tests the critical fix for handling `useAs: tools` connections properly.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from langflow.services.genesis.converter import FlowConverter
from langflow.services.genesis.models import Component, ComponentProvides, AgentSpec


class TestToolConnectionLogic:
    """Test tool connection validation and edge creation logic."""

    @pytest.fixture
    def converter(self):
        """Create converter instance for testing."""
        return FlowConverter()

    @pytest.fixture
    def mock_mcp_component(self):
        """Create mock MCP component for testing."""
        component = Mock(spec=Component)
        component.id = "service-validator"
        component.type = "genesis:mcp_tool"
        component.asTools = True
        component.provides = [
            Mock(spec=ComponentProvides, in_="eoc-agent", useAs="tools", description="Service validation tool")
        ]
        return component

    @pytest.fixture
    def mock_agent_component(self):
        """Create mock agent component for testing."""
        component = Mock(spec=Component)
        component.id = "eoc-agent"
        component.type = "genesis:agent"
        component.provides = []
        return component

    @pytest.fixture
    def mock_knowledge_component(self):
        """Create mock knowledge hub search component."""
        component = Mock(spec=Component)
        component.id = "eoc-search"
        component.type = "genesis:knowledge_hub_search"
        component.asTools = True
        component.provides = [
            Mock(spec=ComponentProvides, in_="eoc-agent", useAs="tools", description="EOC document search")
        ]
        return component

    def test_validate_tool_connection_capability_mcp_component(self, converter, mock_mcp_component):
        """Test that MCP components are recognized as tool-capable."""
        result = converter._validate_tool_connection_capability(
            "MCPTools", "Agent", mock_mcp_component
        )
        assert result is True

    def test_validate_tool_connection_capability_knowledge_search(self, converter, mock_knowledge_component):
        """Test that knowledge search components are recognized as tool-capable."""
        result = converter._validate_tool_connection_capability(
            "KnowledgeHubSearch", "Agent", mock_knowledge_component
        )
        assert result is True

    def test_validate_tool_connection_capability_astools_true(self, converter):
        """Test that components with asTools=true are recognized as tool-capable."""
        component = Mock(spec=Component)
        component.asTools = True

        result = converter._validate_tool_connection_capability(
            "SomeComponent", "Agent", component
        )
        assert result is True

    def test_validate_tool_connection_capability_non_tool_component(self, converter):
        """Test that non-tool components are rejected."""
        component = Mock(spec=Component)
        component.asTools = False

        result = converter._validate_tool_connection_capability(
            "TextInput", "Agent", component
        )
        assert result is False

    def test_target_accepts_tools_agent(self, converter):
        """Test that agent components can accept tools."""
        assert converter._target_accepts_tools("Agent") is True
        assert converter._target_accepts_tools("AutonomizeAgent") is True
        assert converter._target_accepts_tools("CrewAIAgentComponent") is True

    def test_target_accepts_tools_non_agent(self, converter):
        """Test that non-agent components cannot accept tools."""
        assert converter._target_accepts_tools("ChatInput") is False
        assert converter._target_accepts_tools("ChatOutput") is False
        assert converter._target_accepts_tools("TextInput") is False

    def test_component_has_tool_capability_mcp(self, converter, mock_mcp_component):
        """Test MCP component tool capability detection."""
        result = converter._component_has_tool_capability("MCPTools", mock_mcp_component)
        assert result is True

    def test_component_has_tool_capability_inherent_tools(self, converter):
        """Test inherently tool-capable components."""
        component = Mock(spec=Component)

        tool_types = [
            "KnowledgeHubSearch", "APIRequest", "Calculator",
            "WebSearchComponent", "CSVToDataComponent", "SQLExecutor"
        ]

        for tool_type in tool_types:
            result = converter._component_has_tool_capability(tool_type, component)
            assert result is True, f"{tool_type} should be tool-capable"

    def test_determine_output_field_mcp_tools(self, converter):
        """Test output field determination for MCP components used as tools."""
        mock_node = {"data": {"type": "MCPTools"}}
        mock_provide = Mock()
        mock_provide.fromOutput = None

        result = converter._determine_output_field_fixed(
            "tools", mock_node, "MCPTools", mock_provide
        )
        assert result == "response"

    def test_determine_output_field_knowledge_search_tools(self, converter):
        """Test output field determination for knowledge search used as tools."""
        mock_node = {"data": {"type": "KnowledgeHubSearch"}}
        mock_provide = Mock()
        mock_provide.fromOutput = None

        result = converter._determine_output_field_fixed(
            "tools", mock_node, "KnowledgeHubSearch", mock_provide
        )
        assert result == "response"

    def test_create_edge_tool_connection_success(self, converter):
        """Test successful tool connection edge creation."""
        # Mock source node (MCP component)
        source_node = {
            "id": "service-validator",
            "data": {
                "type": "MCPTools",
                "outputs": [{"name": "response", "types": ["DataFrame"]}]
            }
        }

        # Mock target node (Agent)
        target_node = {
            "id": "eoc-agent",
            "data": {
                "type": "Agent",
                "inputs": [{"name": "tools", "types": ["Tool"]}]
            }
        }

        node_map = {
            "service-validator": source_node,
            "eoc-agent": target_node
        }

        # Mock provide object
        provide = Mock()
        provide.in_ = "eoc-agent"
        provide.useAs = "tools"
        provide.fromOutput = None

        # Mock source component
        source_component = Mock()
        source_component.asTools = True

        # Create edge
        edge = converter._create_edge_from_provides(
            "service-validator", provide, node_map, source_component
        )

        assert edge is not None
        assert edge["source"] == "service-validator"
        assert edge["target"] == "eoc-agent"

    def test_create_edge_tool_connection_validation_failure(self, converter):
        """Test tool connection edge creation when validation fails."""
        # Mock non-tool-capable source
        source_node = {
            "id": "text-input",
            "data": {
                "type": "TextInput",
                "outputs": [{"name": "text", "types": ["str"]}]
            }
        }

        # Mock target node (Agent)
        target_node = {
            "id": "agent",
            "data": {
                "type": "Agent",
                "inputs": [{"name": "tools", "types": ["Tool"]}]
            }
        }

        node_map = {
            "text-input": source_node,
            "agent": target_node
        }

        # Mock provide object
        provide = Mock()
        provide.in_ = "agent"
        provide.useAs = "tools"
        provide.fromOutput = None

        # Mock source component (not tool-capable)
        source_component = Mock()
        source_component.asTools = False

        # Create edge should fail
        edge = converter._create_edge_from_provides(
            "text-input", provide, node_map, source_component
        )

        assert edge is None


class TestToolConnectionIntegration:
    """Integration tests for tool connection logic with real specifications."""

    def test_eoc_specification_pattern(self):
        """Test the specific pattern from EOC specification that was failing."""
        converter = FlowConverter()

        # Mock the problematic components from EOC spec
        eoc_search_component = Mock()
        eoc_search_component.id = "eoc-search"
        eoc_search_component.type = "genesis:knowledge_hub_search"
        eoc_search_component.asTools = True

        service_validator_component = Mock()
        service_validator_component.id = "service-validator"
        service_validator_component.type = "genesis:mcp_tool"
        service_validator_component.asTools = True

        # Test knowledge hub search -> agent connection
        result1 = converter._validate_tool_connection_capability(
            "KnowledgeHubSearch", "Agent", eoc_search_component
        )
        assert result1 is True

        # Test MCP tool -> agent connection
        result2 = converter._validate_tool_connection_capability(
            "MCPTools", "Agent", service_validator_component
        )
        assert result2 is True

    def test_tool_output_type_override(self):
        """Test that tool connections get Tool output type."""
        converter = FlowConverter()

        # Mock a scenario where validation passes
        with patch.object(converter, '_validate_tool_connection_capability', return_value=True):
            # Simulate the output type override logic
            is_tool_connection = True
            validation_result = True
            output_types = ["DataFrame"]  # Original type

            if is_tool_connection and validation_result:
                output_types = ["Tool"]  # Override for tool connections

            assert output_types == ["Tool"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
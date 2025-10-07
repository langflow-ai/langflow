"""Tests for Genesis Spec Converter."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from langflow.custom.genesis.spec.converter import FlowConverter
from langflow.custom.genesis.spec.models import AgentSpec
from langflow.custom.genesis.spec.mapper import ComponentMapper
from langflow.custom.genesis.spec.resolver import VariableResolver


class TestFlowConverter:
    """Test FlowConverter class."""

    @pytest.fixture
    def mock_mapper(self):
        """Mock ComponentMapper."""
        mapper = Mock(spec=ComponentMapper)
        mapper.map_component = Mock(return_value={
            "component": "AgentComponent",
            "config": {"model_provider": "OpenAI"}
        })
        mapper.get_component_template = Mock(return_value={
            "template": {"input_value": {"type": "str"}},
            "outputs": [{"name": "response", "type": "Message"}]
        })
        return mapper

    @pytest.fixture
    def mock_resolver(self):
        """Mock VariableResolver."""
        resolver = Mock(spec=VariableResolver)
        resolver.resolve_variables = Mock(return_value={})
        return resolver

    @pytest.fixture
    def converter(self, mock_mapper, mock_resolver):
        """Create FlowConverter with mocked dependencies."""
        return FlowConverter(mapper=mock_mapper, resolver=mock_resolver)

    @pytest.fixture
    def simple_spec_data(self):
        """Simple agent specification data."""
        return {
            "id": "test-agent",
            "name": "Test Agent",
            "description": "A test agent",
            "components": [
                {
                    "id": "chat-input",
                    "name": "Chat Input",
                    "kind": "Input",
                    "type": "genesis:chat_input"
                },
                {
                    "id": "agent-main",
                    "name": "Main Agent",
                    "kind": "Agent",
                    "type": "genesis:agent"
                },
                {
                    "id": "chat-output",
                    "name": "Chat Output",
                    "kind": "Output",
                    "type": "genesis:chat_output"
                }
            ]
        }

    @pytest.fixture
    def complex_spec_data(self):
        """Complex agent specification with tools and connections."""
        return {
            "id": "complex-agent",
            "name": "Complex Agent",
            "description": "An agent with tools",
            "components": [
                {
                    "id": "calculator-tool",
                    "name": "Calculator",
                    "kind": "Tool",
                    "type": "genesis:calculator",
                    "asTools": True,
                    "provides": [
                        {"useAs": "tools", "in": "agent-main"}
                    ]
                },
                {
                    "id": "agent-main",
                    "name": "Main Agent",
                    "kind": "Agent",
                    "type": "genesis:agent"
                },
                {
                    "id": "prompt-template",
                    "name": "System Prompt",
                    "kind": "Prompt",
                    "type": "genesis:prompt",
                    "provides": [
                        {"useAs": "system_prompt", "in": "agent-main"}
                    ]
                }
            ],
            "variables": [
                {
                    "name": "api_key",
                    "type": "string",
                    "required": True,
                    "description": "API key for external service"
                }
            ]
        }

    def test_converter_initialization(self):
        """Test FlowConverter initialization."""
        # Test with default dependencies
        converter = FlowConverter()
        assert converter.mapper is not None
        assert converter.resolver is not None

        # Test with custom dependencies
        mapper = Mock()
        resolver = Mock()
        converter = FlowConverter(mapper=mapper, resolver=resolver)
        assert converter.mapper is mapper
        assert converter.resolver is resolver

    @pytest.mark.asyncio
    async def test_convert_simple_spec(self, converter, simple_spec_data, mock_mapper):
        """Test converting a simple specification."""
        # Mock the component mapping
        mock_mapper.map_component.side_effect = [
            {"component": "ChatInput", "config": {}},
            {"component": "AgentComponent", "config": {}},
            {"component": "ChatOutput", "config": {}}
        ]

        mock_mapper.get_component_template.return_value = {
            "template": {"input_value": {"type": "str"}},
            "outputs": [{"name": "response", "type": "Message"}]
        }

        with patch('langflow.services.spec.component_template_service.component_template_service') as mock_service:
            mock_service.get_component_template.return_value = {
                "template": {"input_value": {"type": "str"}},
                "outputs": [{"name": "response", "type": "Message"}]
            }

            result = await converter.convert(simple_spec_data)

        # Verify the result structure
        assert "id" in result
        assert "name" in result
        assert result["name"] == "Test Agent"
        assert "data" in result
        assert "nodes" in result["data"]
        assert "edges" in result["data"]

        # Should have 3 nodes
        nodes = result["data"]["nodes"]
        assert len(nodes) == 3

        # Verify node IDs match spec component IDs
        node_ids = {node["id"] for node in nodes}
        expected_ids = {"chat-input", "agent-main", "chat-output"}
        assert node_ids == expected_ids

    @pytest.mark.asyncio
    async def test_convert_with_provides_relationships(self, converter, complex_spec_data, mock_mapper):
        """Test converting spec with provides relationships (edges)."""
        # Mock the component mapping
        mock_mapper.map_component.side_effect = [
            {"component": "CalculatorTool", "config": {}},
            {"component": "AgentComponent", "config": {}},
            {"component": "PromptTemplate", "config": {}}
        ]

        mock_mapper.get_component_template.side_effect = [
            {
                "template": {"input": {"type": "str"}},
                "outputs": [{"name": "tool_output", "type": "Tool"}]
            },
            {
                "template": {
                    "tools": {"type": "Tool", "list": True},
                    "system_prompt": {"type": "Message"}
                },
                "outputs": [{"name": "response", "type": "Message"}]
            },
            {
                "template": {"template": {"type": "str"}},
                "outputs": [{"name": "prompt", "type": "Message"}]
            }
        ]

        with patch('langflow.services.spec.component_template_service.component_template_service') as mock_service:
            mock_service.get_component_template.side_effect = mock_mapper.get_component_template.side_effect

            result = await converter.convert(complex_spec_data)

        # Verify edges were created for provides relationships
        edges = result["data"]["edges"]
        assert len(edges) == 2  # calculator->agent and prompt->agent

        # Find edges by target
        tool_edge = next((e for e in edges if "tools" in e.get("targetHandle", "")), None)
        prompt_edge = next((e for e in edges if "system_prompt" in e.get("targetHandle", "")), None)

        assert tool_edge is not None
        assert tool_edge["source"] == "calculator-tool"
        assert tool_edge["target"] == "agent-main"

        assert prompt_edge is not None
        assert prompt_edge["source"] == "prompt-template"
        assert prompt_edge["target"] == "agent-main"

    @pytest.mark.asyncio
    async def test_convert_with_variables(self, converter, complex_spec_data, mock_resolver):
        """Test converting spec with variable resolution."""
        variables = {"api_key": "test-key-123"}
        mock_resolver.resolve_variables.return_value = variables

        with patch('langflow.services.spec.component_template_service.component_template_service'):
            result = await converter.convert(complex_spec_data, variables=variables)

        # Verify resolver was called
        mock_resolver.resolve_variables.assert_called_once()

    @pytest.mark.asyncio
    async def test_edge_id_format(self, converter, complex_spec_data, mock_mapper):
        """Test that edges use correct ID format."""
        mock_mapper.map_component.side_effect = [
            {"component": "CalculatorTool", "config": {}},
            {"component": "AgentComponent", "config": {}},
            {"component": "PromptTemplate", "config": {}}
        ]

        mock_mapper.get_component_template.side_effect = [
            {
                "template": {},
                "outputs": [{"name": "tool_output", "type": "Tool"}]
            },
            {
                "template": {"tools": {"type": "Tool", "list": True}},
                "outputs": [{"name": "response", "type": "Message"}]
            },
            {
                "template": {},
                "outputs": [{"name": "prompt", "type": "Message"}]
            }
        ]

        with patch('langflow.services.spec.component_template_service.component_template_service') as mock_service:
            mock_service.get_component_template.side_effect = mock_mapper.get_component_template.side_effect

            result = await converter.convert(complex_spec_data)

        # Verify edge IDs use correct format (xy-edge__ not reactflow__edge-)
        edges = result["data"]["edges"]
        for edge in edges:
            assert edge["id"].startswith("xy-edge__")

    @pytest.mark.asyncio
    async def test_node_measured_property(self, converter, simple_spec_data, mock_mapper):
        """Test that nodes include measured property."""
        mock_mapper.map_component.return_value = {"component": "AgentComponent", "config": {}}
        mock_mapper.get_component_template.return_value = {
            "template": {"input_value": {"type": "str"}},
            "outputs": [{"name": "response", "type": "Message"}]
        }

        with patch('langflow.services.spec.component_template_service.component_template_service') as mock_service:
            mock_service.get_component_template.return_value = mock_mapper.get_component_template.return_value

            result = await converter.convert(simple_spec_data)

        # Verify all nodes have measured property
        nodes = result["data"]["nodes"]
        for node in nodes:
            assert "measured" in node
            assert "width" in node["measured"]
            assert "height" in node["measured"]

    @pytest.mark.asyncio
    async def test_handle_encoding(self, converter, complex_spec_data, mock_mapper):
        """Test that handles are properly encoded."""
        mock_mapper.map_component.side_effect = [
            {"component": "CalculatorTool", "config": {}},
            {"component": "AgentComponent", "config": {}}
        ]

        mock_mapper.get_component_template.side_effect = [
            {
                "template": {},
                "outputs": [{"name": "tool_output", "type": "Tool"}]
            },
            {
                "template": {"tools": {"type": "Tool", "list": True}},
                "outputs": [{"name": "response", "type": "Message"}]
            }
        ]

        # Simplify spec to focus on one edge
        simplified_spec = {
            **complex_spec_data,
            "components": complex_spec_data["components"][:2]  # Only tool and agent
        }

        with patch('langflow.services.spec.component_template_service.component_template_service') as mock_service:
            mock_service.get_component_template.side_effect = mock_mapper.get_component_template.side_effect

            result = await converter.convert(simplified_spec)

        # Verify handle encoding (quotes replaced with œ)
        edges = result["data"]["edges"]
        assert len(edges) == 1

        edge = edges[0]
        assert "sourceHandle" in edge
        assert "targetHandle" in edge

        # Handles should contain œ instead of quotes
        source_handle = edge["sourceHandle"]
        target_handle = edge["targetHandle"]
        assert "œ" in source_handle
        assert "œ" in target_handle
        assert '"' not in source_handle
        assert '"' not in target_handle

    @pytest.mark.asyncio
    async def test_error_handling_invalid_spec(self, converter):
        """Test error handling for invalid specification."""
        invalid_spec = {
            "name": "Invalid Spec"
            # Missing required fields
        }

        with pytest.raises(Exception):  # Should raise validation error
            await converter.convert(invalid_spec)

    @pytest.mark.asyncio
    async def test_error_handling_mapping_failure(self, converter, simple_spec_data, mock_mapper):
        """Test error handling when component mapping fails."""
        mock_mapper.map_component.side_effect = Exception("Mapping failed")

        with pytest.raises(Exception) as exc_info:
            await converter.convert(simple_spec_data)

        assert "Mapping failed" in str(exc_info.value)

    def test_generate_node_id(self, converter):
        """Test node ID generation."""
        # Test with explicit component ID
        component_data = {"id": "my-component"}
        node_id = converter._generate_node_id(component_data)
        assert node_id == "my-component"

        # Test with missing ID (should generate UUID)
        component_data = {"name": "Component Without ID"}
        node_id = converter._generate_node_id(component_data)
        assert len(node_id) > 10  # Should be a UUID

    def test_generate_flow_metadata(self, converter):
        """Test flow metadata generation."""
        spec_data = {
            "id": "test-flow",
            "name": "Test Flow",
            "description": "A test flow"
        }

        metadata = converter._generate_flow_metadata(spec_data)

        assert metadata["id"] == "test-flow"
        assert metadata["name"] == "Test Flow"
        assert metadata["description"] == "A test flow"
        assert "created_at" in metadata
        assert "updated_at" in metadata
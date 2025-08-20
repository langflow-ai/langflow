import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from langflow.components.agents.mcp_component import MCPToolsComponent
from pydantic import BaseModel, Field


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name="test_tool", description="Test tool"):
        self.name = name
        self.description = description
        self.args_schema = self._create_mock_schema()
        self.coroutine = AsyncMock(return_value=MagicMock(content=[]))

    def _create_mock_schema(self):
        """Create a mock schema for the tool."""

        class MockSchema(BaseModel):
            query: str = Field(..., description="Query parameter")

        MockSchema.schema = lambda: {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Query parameter"}},
            "required": ["query"],
        }
        return MockSchema


class TestMCPToolsComponent:
    """Test cases for MCPToolsComponent."""

    @pytest.fixture
    def component(self):
        """Create an MCPToolsComponent instance for testing."""
        with (
            patch("langflow.components.agents.mcp_component.MCPStdioClient"),
            patch("langflow.components.agents.mcp_component.MCPSseClient"),
        ):
            return MCPToolsComponent()

    def test_component_initialization(self, component):
        """Test proper initialization of MCPToolsComponent."""
        assert component.display_name == "MCP Tools"
        assert component.description == "Connect to an MCP server to use its tools."
        assert component.name == "MCPTools"
        assert component.icon == "Mcp"
        assert hasattr(component, "_shared_component_cache")

    def test_component_attributes(self, component):
        """Test component attributes are properly initialized."""
        assert component.schema_inputs == []
        assert component.tools == []
        assert component._not_load_actions is False
        assert isinstance(component._tool_cache, dict)
        assert component._last_selected_server is None

    def test_inputs_configuration(self, component):
        """Test that inputs are properly configured."""
        expected_input_names = {"mcp_server", "tool", "tool_placeholder"}
        input_names = {inp.name for inp in component.inputs}
        assert expected_input_names == input_names

        # Test mcp_server input
        mcp_server_input = next(inp for inp in component.inputs if inp.name == "mcp_server")
        assert mcp_server_input.display_name == "MCP Server"
        assert mcp_server_input.real_time_refresh is True

        # Test tool input
        tool_input = next(inp for inp in component.inputs if inp.name == "tool")
        assert tool_input.display_name == "Tool"
        assert tool_input.show is False
        assert tool_input.required is True
        assert tool_input.real_time_refresh is True

    def test_outputs_configuration(self, component):
        """Test that outputs are properly configured."""
        assert len(component.outputs) == 1
        output = component.outputs[0]
        assert output.name == "response"
        assert output.display_name == "Response"
        assert output.method == "build_output"

    def test_default_keys(self, component):
        """Test default keys are properly defined."""
        expected_keys = [
            "code",
            "_type",
            "tool_mode",
            "tool_placeholder",
            "mcp_server",
            "tool",
        ]
        assert component.default_keys == expected_keys

    @patch("langflow.components.agents.mcp_component.safe_cache_get")
    @patch("langflow.components.agents.mcp_component.safe_cache_set")
    def test_ensure_cache_structure(self, mock_cache_set, mock_cache_get, component):
        """Test cache structure initialization."""
        # Mock cache_get to return None (missing keys)
        mock_cache_get.return_value = None

        component._ensure_cache_structure()

        # Verify cache_get was called for both keys
        assert mock_cache_get.call_count == 2
        mock_cache_get.assert_any_call(component._shared_component_cache, "servers")
        mock_cache_get.assert_any_call(component._shared_component_cache, "last_selected_server")

        # Verify cache_set was called for both keys
        assert mock_cache_set.call_count == 2
        mock_cache_set.assert_any_call(component._shared_component_cache, "servers", {})
        mock_cache_set.assert_any_call(component._shared_component_cache, "last_selected_server", "")

    @patch("langflow.components.agents.mcp_component.safe_cache_get")
    @patch("langflow.components.agents.mcp_component.safe_cache_set")
    def test_ensure_cache_structure_existing_keys(self, mock_cache_set, mock_cache_get, component):
        """Test cache structure with existing keys."""
        # Mock cache_get to return existing values
        mock_cache_get.side_effect = [{"existing": "data"}, "existing_server"]

        component._ensure_cache_structure()

        # Verify cache_get was called
        assert mock_cache_get.call_count == 2

        # Verify cache_set was NOT called since keys already exist
        mock_cache_set.assert_not_called()

    def test_component_inheritance(self, component):
        """Test that component properly inherits from ComponentWithCache."""
        from langflow.custom.custom_component.component_with_cache import ComponentWithCache

        assert isinstance(component, ComponentWithCache)

    async def test_validate_schema_inputs_valid_tool(self, component):
        """Test _validate_schema_inputs with valid tool."""
        mock_tool = MockTool()

        with (
            patch("langflow.components.agents.mcp_component.flatten_schema") as mock_flatten,
            patch(
                "langflow.components.agents.mcp_component.create_input_schema_from_json_schema"
            ) as mock_create_schema,
            patch("langflow.components.agents.mcp_component.schema_to_langflow_inputs") as mock_to_langflow,
        ):
            # Mock the schema processing chain
            mock_flatten.return_value = {"query": {"type": "string"}}
            mock_create_schema.return_value = {"query": {"type": "string"}}
            mock_schema_input = Mock()
            mock_schema_input.name = "query"
            mock_to_langflow.return_value = [mock_schema_input]

            result = await component._validate_schema_inputs(mock_tool)

            assert len(result) == 1
            assert result[0].name == "query"
            mock_flatten.assert_called_once()
            mock_create_schema.assert_called_once()
            mock_to_langflow.assert_called_once()

    async def test_validate_schema_inputs_invalid_tool(self, component):
        """Test _validate_schema_inputs with invalid tool."""
        with pytest.raises(ValueError, match="Invalid tool object or missing input schema"):
            await component._validate_schema_inputs(None)

        mock_tool_no_schema = Mock()
        mock_tool_no_schema.name = "test"
        # Remove args_schema attribute
        del mock_tool_no_schema.args_schema

        with pytest.raises(ValueError, match="Invalid tool object or missing input schema"):
            await component._validate_schema_inputs(mock_tool_no_schema)

    async def test_validate_schema_inputs_empty_schema(self, component):
        """Test _validate_schema_inputs with empty schema."""
        mock_tool = MockTool()

        with (
            patch("langflow.components.agents.mcp_component.flatten_schema") as mock_flatten,
            patch(
                "langflow.components.agents.mcp_component.create_input_schema_from_json_schema"
            ) as mock_create_schema,
        ):
            mock_flatten.return_value = {"query": {"type": "string"}}
            mock_create_schema.return_value = None

            with pytest.raises(ValueError, match="Empty input schema for tool"):
                await component._validate_schema_inputs(mock_tool)

    async def test_validate_schema_inputs_no_langflow_inputs(self, component):
        """Test _validate_schema_inputs with no langflow inputs."""
        mock_tool = MockTool()

        with (
            patch("langflow.components.agents.mcp_component.flatten_schema") as mock_flatten,
            patch(
                "langflow.components.agents.mcp_component.create_input_schema_from_json_schema"
            ) as mock_create_schema,
            patch("langflow.components.agents.mcp_component.schema_to_langflow_inputs") as mock_to_langflow,
        ):
            mock_flatten.return_value = {"query": {"type": "string"}}
            mock_create_schema.return_value = {"query": {"type": "string"}}
            mock_to_langflow.return_value = []

            result = await component._validate_schema_inputs(mock_tool)

            assert result == []

    async def test_validate_schema_inputs_exception(self, component):
        """Test _validate_schema_inputs with exception during processing."""
        mock_tool = MockTool()

        with patch("langflow.components.agents.mcp_component.flatten_schema", side_effect=Exception("Test error")):
            with pytest.raises(ValueError, match="Error validating schema inputs"):
                await component._validate_schema_inputs(mock_tool)

    async def test_update_tool_list_no_server(self, component):
        """Test update_tool_list with no server specified."""
        result_tools, result_server_info = await component.update_tool_list()

        assert result_tools == []
        assert component.tools == []
        assert result_server_info["name"] is None
        assert result_server_info["config"] is None

    def test_update_tool_list_dict_server_input_no_config(self, component):
        """Test update_tool_list with dictionary server input but no valid config."""
        server_dict = {"name": "test_server", "config": {"url": "test://url"}}

        async def run_test():
            with patch("langflow.components.agents.mcp_component.safe_cache_get") as mock_cache_get:
                mock_cache_get.return_value = {}

                tools, server_info = await component.update_tool_list(server_dict)

                assert server_info["name"] == "test_server"
                assert server_info["config"] == server_dict["config"]
                assert tools == []  # No tools since server config not found

        import asyncio

        asyncio.run(run_test())

    @patch("langflow.components.agents.mcp_component.safe_cache_get")
    def test_update_tool_list_cached_server(self, mock_cache_get, component):
        """Test update_tool_list with cached server data."""
        server_name = "cached_server"
        cached_data = {
            "tools": [MockTool()],
            "tool_names": ["test_tool"],
            "tool_cache": {"test_tool": "cached"},
            "config": {"cached": True},
        }

        # Mock cache to return cached data
        mock_cache_get.return_value = {server_name: cached_data}

        async def run_test():
            tools, server_info = await component.update_tool_list(server_name)

            assert tools == cached_data["tools"]
            assert component.tools == cached_data["tools"]
            assert component.tool_names == cached_data["tool_names"]
            assert component._tool_cache == cached_data["tool_cache"]
            assert server_info["config"] == cached_data["config"]

        asyncio.run(run_test())

    def test_get_inputs_for_all_tools_valid_tools(self, component):
        """Test get_inputs_for_all_tools with valid tools."""
        mock_tools = [MockTool(name="tool1"), MockTool(name="tool2")]

        with (
            patch("langflow.components.agents.mcp_component.flatten_schema") as mock_flatten,
            patch(
                "langflow.components.agents.mcp_component.create_input_schema_from_json_schema"
            ) as mock_create_schema,
            patch("langflow.components.agents.mcp_component.schema_to_langflow_inputs") as mock_to_langflow,
        ):
            mock_flatten.return_value = {"query": {"type": "string"}}
            mock_create_schema.return_value = {"query": {"type": "string"}}
            mock_input = Mock()
            mock_input.name = "query"
            mock_to_langflow.return_value = [mock_input]

            result = component.get_inputs_for_all_tools(mock_tools)

            assert len(result) == 2
            assert "tool1" in result
            assert "tool2" in result
            assert len(result["tool1"]) == 1
            assert len(result["tool2"]) == 1

    def test_get_inputs_for_all_tools_invalid_tools(self, component):
        """Test get_inputs_for_all_tools with invalid tools."""
        # Test with None tool
        mock_tools = [None, MockTool(name="valid_tool")]

        with (
            patch("langflow.components.agents.mcp_component.flatten_schema") as mock_flatten,
            patch(
                "langflow.components.agents.mcp_component.create_input_schema_from_json_schema"
            ) as mock_create_schema,
            patch("langflow.components.agents.mcp_component.schema_to_langflow_inputs") as mock_to_langflow,
        ):
            mock_flatten.return_value = {"query": {"type": "string"}}
            mock_create_schema.return_value = {"query": {"type": "string"}}
            mock_input = Mock()
            mock_input.name = "query"
            mock_to_langflow.return_value = [mock_input]

            result = component.get_inputs_for_all_tools(mock_tools)

            # Should only process the valid tool
            assert len(result) == 1
            assert "valid_tool" in result

    def test_get_inputs_for_all_tools_exception(self, component):
        """Test get_inputs_for_all_tools with exception during processing."""
        mock_tool = MockTool(name="error_tool")

        with patch(
            "langflow.components.agents.mcp_component.flatten_schema", side_effect=AttributeError("Schema error")
        ):
            result = component.get_inputs_for_all_tools([mock_tool])

            # Should handle exception and continue processing
            assert result == {}

    def test_remove_input_schema_from_build_config(self, component):
        """Test remove_input_schema_from_build_config method."""
        build_config = {
            "tool1_param": {"value": "test1"},
            "tool2_param": {"value": "test2"},
            "default_param": {"value": "default"},
        }

        mock_input1 = Mock()
        mock_input1.name = "tool1_param"
        mock_input2 = Mock()
        mock_input2.name = "tool2_param"

        input_schema = {
            "tool1": [mock_input1],
            "tool2": [mock_input2],
        }

        component.remove_input_schema_from_build_config(build_config, "tool1", input_schema)

        # Should remove inputs from tool2 but not tool1
        assert "tool1_param" in build_config  # This tool should be kept
        assert "tool2_param" not in build_config  # This should be removed
        assert "default_param" in build_config  # This should remain

    def test_remove_non_default_keys(self, component):
        """Test remove_non_default_keys method."""
        build_config = {
            "code": "keep",
            "_type": "keep",
            "tool_mode": "keep",
            "custom_param": "remove",
            "another_custom": "remove",
            "mcp_server": "keep",
            "tool": "keep",
            "tool_placeholder": "keep",
        }

        component.remove_non_default_keys(build_config)

        # Should only keep default keys
        expected_keys = set(component.default_keys)
        remaining_keys = set(build_config.keys())
        assert remaining_keys == expected_keys

    def test_get_session_context_returns_none_by_default(self, component):
        """Test _get_session_context returns None when no graph context available."""
        # Most components won't have graph context in testing
        result = component._get_session_context()
        assert result is None

    async def test_get_tools_not_load_actions_false(self, component):
        """Test _get_tools when _not_load_actions is False."""
        component._not_load_actions = False
        component.mcp_server = "test_server"

        with patch.object(component, "update_tool_list") as mock_update:
            mock_tools = [MockTool()]
            mock_update.return_value = (mock_tools, {"name": "test_server", "config": {}})

            result = await component._get_tools()

            assert result == mock_tools
            mock_update.assert_called_once_with("test_server")

    async def test_get_tools_not_load_actions_true(self, component):
        """Test _get_tools when _not_load_actions is True."""
        component._not_load_actions = True

        result = await component._get_tools()

        assert result == []

    async def test_update_build_config_tool_field_with_timeout(self, component):
        """Test update_build_config when tool update times out."""
        build_config = {
            "tool": {"show": False, "options": [], "value": "", "placeholder": ""},
            "tools_metadata": {"show": False},
            "mcp_server": {"value": "test_server"},
        }

        component.tools = []

        with patch.object(component, "update_tool_list") as mock_update:
            mock_update.side_effect = asyncio.TimeoutError("Timeout")

            result = await component.update_build_config(build_config, "", "tool")

            assert result["tool"]["show"] is True
            assert result["tool"]["options"] == []
            assert result["tool"]["placeholder"] == "Timeout on MCP server"

    async def test_update_build_config_tool_field_with_value_error(self, component):
        """Test update_build_config when tool update raises ValueError."""
        build_config = {
            "tool": {"show": False, "options": [], "value": "", "placeholder": ""},
            "tools_metadata": {"show": False},
            "mcp_server": {"value": "test_server"},
        }

        component.tools = []

        with patch.object(component, "update_tool_list") as mock_update:
            mock_update.side_effect = ValueError("Server error")

            result = await component.update_build_config(build_config, "", "tool")

            assert result["tool"]["show"] is True
            assert result["tool"]["options"] == []
            assert result["tool"]["placeholder"] == "Error on MCP Server"

    async def test_update_build_config_tools_metadata_field(self, component):
        """Test update_build_config when tools_metadata field changes."""
        build_config = {"some_field": "value"}

        result = await component.update_build_config(build_config, True, "tools_metadata")

        assert component._not_load_actions is False
        assert result == build_config

    async def test_update_build_config_mcp_server_field_empty_value(self, component):
        """Test update_build_config when mcp_server field is empty."""
        build_config = {
            "tool": {"show": True, "options": ["test"], "value": "test", "placeholder": "test"},
            "tool_placeholder": {"tool_mode": True},
        }

        result = await component.update_build_config(build_config, "", "mcp_server")

        assert result["tool"]["show"] is False
        assert result["tool"]["options"] == []
        assert result["tool"]["value"] == ""
        assert result["tool"]["placeholder"] == ""
        assert result["tool_placeholder"]["tool_mode"] is False

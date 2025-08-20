import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from langflow.components.agents.mcp_component import MCPToolsComponent
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
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

    async def test_update_tool_list_dict_server_input(self, component):
        """Test update_tool_list with dictionary server input."""
        server_dict = {"name": "test_server", "config": {"url": "test://url"}}

        with patch("langflow.components.agents.mcp_component.safe_cache_get") as mock_cache_get:
            mock_cache_get.return_value = {}

            with patch.object(component, "_update_tools_from_server") as mock_update:
                mock_tools = [MockTool()]
                mock_update.return_value = (mock_tools, server_dict["config"])

                # Mock the async dependencies
                with (
                    patch("langflow.components.agents.mcp_component.get_session"),
                    patch(
                        "langflow.components.agents.mcp_component.create_user_longterm_token",
                        return_value=("user1", None),
                    ),
                    patch("langflow.components.agents.mcp_component.get_user_by_id", return_value=Mock()),
                    patch("langflow.components.agents.mcp_component.get_server", return_value=server_dict["config"]),
                    patch("langflow.components.agents.mcp_component.update_tools", return_value=(None, mock_tools, {})),
                ):
                    tools, server_info = await component.update_tool_list(server_dict)

                    assert server_info["name"] == "test_server"
                    assert server_info["config"] == server_dict["config"]

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

    async def test_update_tool_list_timeout_error(self, component):
        """Test update_tool_list with timeout error."""
        server_name = "timeout_server"

        with patch("langflow.components.agents.mcp_component.safe_cache_get") as mock_cache_get:
            mock_cache_get.return_value = {}

            # Mock the database operations to raise TimeoutError
            with (
                patch("langflow.components.agents.mcp_component.get_session"),
                patch(
                    "langflow.components.agents.mcp_component.create_user_longterm_token",
                    side_effect=asyncio.TimeoutError("Connection timeout"),
                ),
            ):
                with pytest.raises(TimeoutError, match="Timeout updating tool list"):
                    await component.update_tool_list(server_name)

    async def test_update_tool_list_general_exception(self, component):
        """Test update_tool_list with general exception."""
        server_name = "error_server"

        with patch("langflow.components.agents.mcp_component.safe_cache_get") as mock_cache_get:
            mock_cache_get.return_value = {}

            # Mock the database operations to raise a general exception
            with (
                patch("langflow.components.agents.mcp_component.get_session"),
                patch(
                    "langflow.components.agents.mcp_component.create_user_longterm_token",
                    side_effect=ValueError("Database error"),
                ),
            ):
                with pytest.raises(ValueError, match="Error updating tool list"):
                    await component.update_tool_list(server_name)

    async def test_update_build_config_tool_field_empty_tools(self, component):
        """Test update_build_config when tool field is selected but no tools available."""
        build_config = {
            "tool": {"show": False, "options": [], "value": "", "placeholder": ""},
            "tools_metadata": {"show": False},
            "mcp_server": {"value": "test_server"},
        }

        component.tools = []

        with patch.object(component, "update_tool_list") as mock_update:
            mock_update.return_value = ([], {"name": "test_server", "config": {}})

            result = await component.update_build_config(build_config, "", "tool")

            assert result["tool"]["show"] is True
            assert result["tool"]["options"] == []
            assert result["tool"]["placeholder"] == "Select a tool"

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

    async def test_update_build_config_tool_field_valid_tool(self, component):
        """Test update_build_config with valid tool selection."""
        build_config = {
            "tool": {"show": True, "options": ["test_tool"], "value": "test_tool", "placeholder": ""},
            "tools_metadata": {"show": False},
        }

        mock_tool = MockTool()
        component.tools = [mock_tool]

        with patch.object(component, "_update_tool_config") as mock_update_config:
            result = await component.update_build_config(build_config, "test_tool", "tool")

            mock_update_config.assert_called_once_with(build_config, "test_tool")
            assert result == build_config

    async def test_update_build_config_tool_field_tool_not_found(self, component):
        """Test update_build_config when selected tool is not found."""
        build_config = {
            "tool": {"show": True, "options": ["other_tool"], "value": "nonexistent_tool", "placeholder": ""},
            "tools_metadata": {"show": False},
        }

        mock_tool = MockTool(name="other_tool")
        component.tools = [mock_tool]

        result = await component.update_build_config(build_config, "nonexistent_tool", "tool")

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

    async def test_update_build_config_mcp_server_field_with_value(self, component):
        """Test update_build_config when mcp_server field has value."""
        build_config = {
            "tool": {"show": False, "options": [], "value": "", "placeholder": ""},
            "tool_placeholder": {"tool_mode": False},
            "tools_metadata": {"show": False},
        }

        server_name = "new_server"

        with (
            patch("langflow.components.agents.mcp_component.safe_cache_get") as mock_cache_get,
            patch("langflow.components.agents.mcp_component.safe_cache_set") as mock_cache_set,
            patch.object(component, "remove_non_default_keys") as mock_remove,
        ):
            mock_cache_get.side_effect = [None, {}]  # last_selected_server, servers cache

            result = await component.update_build_config(build_config, server_name, "mcp_server")

            assert result["tool_placeholder"]["tool_mode"] is True
            assert result["tool"]["show"] is True
            mock_cache_set.assert_called_with(component._shared_component_cache, "last_selected_server", server_name)
            mock_remove.assert_called_once()

    async def test_update_build_config_tool_mode_field(self, component):
        """Test update_build_config when tool_mode field changes."""
        build_config = {
            "tool": {"show": True, "value": "current_tool", "options": [], "placeholder": "test"},
            "mcp_server": {"value": "test_server"},
        }

        with patch.object(component, "remove_non_default_keys") as mock_remove:
            # Test tool_mode = True (hide tool dropdown)
            result = await component.update_build_config(build_config, True, "tool_mode")

            assert result["tool"]["show"] is False
            assert result["tool"]["placeholder"] == ""
            assert component._not_load_actions is True
            assert component.tool == "current_tool"
            mock_remove.assert_called_once()

    async def test_update_build_config_tools_metadata_field(self, component):
        """Test update_build_config when tools_metadata field changes."""
        build_config = {"some_field": "value"}

        result = await component.update_build_config(build_config, True, "tools_metadata")

        assert component._not_load_actions is False
        assert result == build_config

    async def test_update_build_config_exception(self, component):
        """Test update_build_config with exception during processing."""
        build_config = {"tool": {"show": True}}

        # Force an exception by accessing non-existent attribute
        with patch.object(component, "remove_non_default_keys", side_effect=AttributeError("Test error")):
            with pytest.raises(ValueError, match="Error in update_build_config"):
                await component.update_build_config(build_config, "", "mcp_server")

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

        input_schema = {
            "tool1": [Mock(name="tool1_param")],
            "tool2": [Mock(name="tool2_param")],
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
        }

        component.remove_non_default_keys(build_config)

        # Should only keep default keys
        expected_keys = set(component.default_keys)
        remaining_keys = set(build_config.keys())
        assert remaining_keys == expected_keys

    async def test_update_tool_config_no_tools(self, component):
        """Test _update_tool_config when no tools are available."""
        build_config = {"mcp_server": {"value": "test_server"}}

        with patch.object(component, "update_tool_list") as mock_update:
            mock_update.return_value = ([], {"name": "test_server", "config": {}})

            await component._update_tool_config(build_config, "test_tool")

            mock_update.assert_called_once()

    async def test_update_tool_config_no_tool_name(self, component):
        """Test _update_tool_config with empty tool name."""
        build_config = {}
        component.tools = [MockTool()]

        await component._update_tool_config(build_config, "")

        # Should return early without doing anything
        assert build_config == {}

    async def test_update_tool_config_tool_not_found(self, component):
        """Test _update_tool_config when tool is not found."""
        build_config = {"tool": {"value": "test_tool"}}
        component.tools = [MockTool(name="other_tool")]

        with patch.object(component, "remove_non_default_keys") as mock_remove:
            await component._update_tool_config(build_config, "nonexistent_tool")

            mock_remove.assert_called_once_with(build_config)
            assert build_config["tool"]["value"] == ""

    async def test_update_tool_config_valid_tool(self, component):
        """Test _update_tool_config with valid tool."""
        build_config = {
            "tool": {"value": "test_tool"},
            "old_param": {"value": "old_value"},
        }
        mock_tool = MockTool(name="test_tool")
        component.tools = [mock_tool]

        with (
            patch.object(component, "get_inputs_for_all_tools") as mock_get_inputs,
            patch.object(component, "remove_input_schema_from_build_config") as mock_remove_schema,
            patch.object(component, "_validate_schema_inputs") as mock_validate,
        ):
            mock_get_inputs.return_value = {"test_tool": []}
            mock_schema_input = Mock()
            mock_schema_input.name = "new_param"
            mock_schema_input.to_dict.return_value = {"name": "new_param", "type": "string"}
            mock_validate.return_value = [mock_schema_input]

            await component._update_tool_config(build_config, "test_tool")

            mock_validate.assert_called_once_with(mock_tool)
            mock_remove_schema.assert_called_once()
            assert "new_param" in build_config

    async def test_update_tool_config_no_schema_inputs(self, component):
        """Test _update_tool_config when tool has no schema inputs."""
        build_config = {"tool": {"value": "test_tool"}}
        mock_tool = MockTool(name="test_tool")
        component.tools = [mock_tool]

        with (
            patch.object(component, "get_inputs_for_all_tools") as mock_get_inputs,
            patch.object(component, "remove_input_schema_from_build_config"),
            patch.object(component, "_validate_schema_inputs") as mock_validate,
        ):
            mock_get_inputs.return_value = {"test_tool": []}
            mock_validate.return_value = []  # No inputs

            await component._update_tool_config(build_config, "test_tool")

            # Should handle case with no inputs gracefully
            assert component.schema_inputs == []

    async def test_update_tool_config_validation_error(self, component):
        """Test _update_tool_config with validation error."""
        build_config = {"tool": {"value": "test_tool"}}
        mock_tool = MockTool(name="test_tool")
        component.tools = [mock_tool]

        with (
            patch.object(component, "get_inputs_for_all_tools"),
            patch.object(component, "remove_input_schema_from_build_config"),
            patch.object(component, "_validate_schema_inputs") as mock_validate,
        ):
            mock_validate.side_effect = ValueError("Validation failed")

            await component._update_tool_config(build_config, "test_tool")

            # Should handle validation error gracefully
            assert component.schema_inputs == []

    async def test_update_tool_config_processing_error(self, component):
        """Test _update_tool_config with error during schema processing."""
        build_config = {"tool": {"value": "test_tool"}}
        mock_tool = MockTool(name="test_tool")
        component.tools = [mock_tool]

        with patch.object(component, "get_inputs_for_all_tools") as mock_get_inputs:
            mock_get_inputs.side_effect = AttributeError("Processing error")

            with pytest.raises(ValueError, match="Error updating tool config"):
                await component._update_tool_config(build_config, "test_tool")

    async def test_build_output_no_tool_selected(self, component):
        """Test build_output when no tool is selected."""
        component.tool = ""

        with patch.object(component, "update_tool_list") as mock_update:
            mock_update.return_value = ([], {"name": "", "config": {}})

            result = await component.build_output()

            assert isinstance(result, DataFrame)
            assert result.data == [{"error": "You must select a tool"}]

    async def test_build_output_with_tool_execution(self, component):
        """Test build_output with successful tool execution."""
        component.tool = "test_tool"
        mock_tool = MockTool(name="test_tool")
        component._tool_cache = {"test_tool": mock_tool}

        # Mock tool execution result
        mock_content_item = Mock()
        mock_content_item.model_dump.return_value = {"type": "text", "content": "result"}
        mock_result = Mock()
        mock_result.content = [mock_content_item]
        mock_tool.coroutine.return_value = mock_result

        with (
            patch.object(component, "update_tool_list") as mock_update,
            patch.object(component, "get_inputs_for_all_tools") as mock_get_inputs,
            patch.object(component, "_get_session_context") as mock_session,
        ):
            mock_update.return_value = ([mock_tool], {"name": "test_server", "config": {}})
            mock_arg = Mock()
            mock_arg.name = "query"
            mock_get_inputs.return_value = {"test_tool": [mock_arg]}
            mock_session.return_value = "session_123"

            # Set component attribute for the argument
            component.query = "test query"

            result = await component.build_output()

            assert isinstance(result, DataFrame)
            assert len(result.data) == 1
            assert result.data[0] == {"type": "text", "content": "result"}

    async def test_build_output_with_message_input(self, component):
        """Test build_output when tool argument is a Message object."""
        component.tool = "test_tool"
        mock_tool = MockTool(name="test_tool")
        component._tool_cache = {"test_tool": mock_tool}

        # Mock tool execution result
        mock_content_item = Mock()
        mock_content_item.model_dump.return_value = {"type": "text", "content": "result"}
        mock_result = Mock()
        mock_result.content = [mock_content_item]
        mock_tool.coroutine.return_value = mock_result

        with (
            patch.object(component, "update_tool_list") as mock_update,
            patch.object(component, "get_inputs_for_all_tools") as mock_get_inputs,
            patch.object(component, "_get_session_context") as mock_session,
        ):
            mock_update.return_value = ([mock_tool], {"name": "test_server", "config": {}})
            mock_arg = Mock()
            mock_arg.name = "message_param"
            mock_get_inputs.return_value = {"test_tool": [mock_arg]}
            mock_session.return_value = "session_123"

            # Set component attribute as Message object
            test_message = Message(text="test message content")
            component.message_param = test_message

            await component.build_output()

            # Verify that Message.text was used as argument
            mock_tool.coroutine.assert_called_once_with(message_param="test message content")

    async def test_build_output_exception(self, component):
        """Test build_output with exception during execution."""
        component.tool = "test_tool"

        with patch.object(component, "update_tool_list") as mock_update:
            mock_update.side_effect = Exception("Tool update failed")

            with pytest.raises(ValueError, match="Error in build_output"):
                await component.build_output()

    def test_get_session_context_with_graph(self, component):
        """Test _get_session_context when component has graph with session_id."""
        mock_graph = Mock()
        mock_graph.session_id = "session_123"
        component.graph = mock_graph
        component.mcp_server = "test_server"

        result = component._get_session_context()

        assert result == "session_123_test_server"

    def test_get_session_context_with_dict_server(self, component):
        """Test _get_session_context with dictionary mcp_server."""
        mock_graph = Mock()
        mock_graph.session_id = "session_456"
        component.graph = mock_graph
        component.mcp_server = {"name": "dict_server", "config": {}}

        result = component._get_session_context()

        assert result == "session_456_dict_server"

    def test_get_session_context_no_graph(self, component):
        """Test _get_session_context when component has no graph."""
        # Mock hasattr to return False for graph
        with patch("builtins.hasattr", side_effect=lambda obj, attr: attr != "graph"):
            result = component._get_session_context()

            assert result is None

    def test_get_session_context_no_session_id(self, component):
        """Test _get_session_context when graph has no session_id."""
        mock_graph = Mock()
        mock_graph.session_id = None
        component.graph = mock_graph
        component.mcp_server = "test_server"

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

    async def test_build_output_with_session_context(self, component):
        """Test build_output sets session context on clients."""
        component.tool = "test_tool"
        mock_tool = MockTool(name="test_tool")
        component._tool_cache = {"test_tool": mock_tool}

        # Mock tool execution
        mock_content_item = Mock()
        mock_content_item.model_dump.return_value = {"result": "success"}
        mock_result = Mock()
        mock_result.content = [mock_content_item]
        mock_tool.coroutine.return_value = mock_result

        with (
            patch.object(component, "update_tool_list") as mock_update,
            patch.object(component, "get_inputs_for_all_tools") as mock_get_inputs,
            patch.object(component, "_get_session_context") as mock_session,
        ):
            mock_update.return_value = ([mock_tool], {"name": "test_server", "config": {}})
            mock_get_inputs.return_value = {"test_tool": []}
            mock_session.return_value = "test_session_context"

            # Mock clients
            mock_stdio_client = Mock()
            mock_sse_client = Mock()
            component.stdio_client = mock_stdio_client
            component.sse_client = mock_sse_client

            await component.build_output()

            # Verify session context was set on both clients
            mock_stdio_client.set_session_context.assert_called_once_with("test_session_context")
            mock_sse_client.set_session_context.assert_called_once_with("test_session_context")

    async def test_build_output_unflatten_kwargs(self, component):
        """Test build_output properly unflattens kwargs before tool execution."""
        component.tool = "test_tool"
        mock_tool = MockTool(name="test_tool")
        component._tool_cache = {"test_tool": mock_tool}

        # Mock tool execution
        mock_content_item = Mock()
        mock_content_item.model_dump.return_value = {"result": "success"}
        mock_result = Mock()
        mock_result.content = [mock_content_item]
        mock_tool.coroutine.return_value = mock_result

        with (
            patch.object(component, "update_tool_list") as mock_update,
            patch.object(component, "get_inputs_for_all_tools") as mock_get_inputs,
            patch("langflow.components.agents.mcp_component.maybe_unflatten_dict") as mock_unflatten,
        ):
            mock_update.return_value = ([mock_tool], {"name": "test_server", "config": {}})
            mock_arg = Mock()
            mock_arg.name = "nested__param"
            mock_get_inputs.return_value = {"test_tool": [mock_arg]}

            # Set flattened parameter
            component.nested__param = "flattened_value"

            # Mock unflatten to return nested dict
            mock_unflatten.return_value = {"nested": {"param": "flattened_value"}}

            await component.build_output()

            # Verify unflatten was called and tool received unflattened kwargs
            mock_unflatten.assert_called_once_with({"nested__param": "flattened_value"})
            mock_tool.coroutine.assert_called_once_with(nested={"param": "flattened_value"})

"""Tests for MCP component."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.tools import StructuredTool

from lfx.components.agents.mcp_component import MCPToolsComponent
from lfx.schema.message import Message


class TestMCPToolsComponent:
    """Test the MCPToolsComponent class."""

    @pytest.fixture
    def component(self):
        """Create a test component instance."""
        return MCPToolsComponent()

    def test_component_initialization(self, component):
        """Test component initializes correctly."""
        assert component.display_name == "MCP Tools"
        assert component.name == "MCPTools"
        assert component.icon == "Mcp"
        assert hasattr(component, "stdio_client")
        assert hasattr(component, "sse_client")
        assert component._last_selected_server is None
        assert isinstance(component._tool_cache, dict)

    def test_ensure_cache_structure(self, component):
        """Test cache structure initialization."""
        # Cache should be initialized in __init__
        cache = component._shared_component_cache

        # Mock the cache get/set methods
        with (
            patch("lfx.components.agents.mcp_component.safe_cache_get") as mock_get,
            patch("lfx.components.agents.mcp_component.safe_cache_set") as mock_set,
        ):
            # Simulate empty cache
            mock_get.return_value = None

            # Call the method
            component._ensure_cache_structure()

            # Should set both servers and last_selected_server
            assert mock_set.call_count == 2
            mock_set.assert_any_call(cache, "servers", {})
            mock_set.assert_any_call(cache, "last_selected_server", "")

    def test_default_keys(self, component):
        """Test default keys are set correctly."""
        expected_keys = [
            "code",
            "_type",
            "tool_mode",
            "tool_placeholder",
            "mcp_server",
            "tool",
        ]
        assert component.default_keys == expected_keys

    def test_inputs_configuration(self, component):
        """Test component inputs are configured correctly."""
        assert len(component.inputs) == 3

        # Check MCP server input
        mcp_input = component.inputs[0]
        assert mcp_input.name == "mcp_server"
        assert mcp_input.display_name == "MCP Server"
        assert mcp_input.real_time_refresh is True

        # Check tool dropdown input
        tool_input = component.inputs[1]
        assert tool_input.name == "tool"
        assert tool_input.display_name == "Tool"
        assert tool_input.show is False
        assert tool_input.required is True
        assert tool_input.real_time_refresh is True

        # Check tool placeholder input
        placeholder_input = component.inputs[2]
        assert placeholder_input.name == "tool_placeholder"
        assert placeholder_input.display_name == "Tool Placeholder"
        assert placeholder_input.show is False

    def test_outputs_configuration(self, component):
        """Test component outputs are configured correctly."""
        assert len(component.outputs) == 1
        output = component.outputs[0]
        assert output.name == "response"
        assert output.display_name == "Response"
        assert output.method == "build_output"

    @pytest.mark.asyncio
    async def test_update_tool_list_stdio(self, component):
        """Test updating tool list with stdio client."""
        # Mock the update_tools function
        mock_tools = [
            Mock(spec=StructuredTool, name="tool1", description="Tool 1"),
            Mock(spec=StructuredTool, name="tool2", description="Tool 2"),
        ]

        with patch("lfx.components.agents.mcp_component.update_tools") as mock_update:
            mock_update.return_value = ("Stdio", mock_tools, {"tool1": mock_tools[0], "tool2": mock_tools[1]})

            # Simulate server config
            server_name = "test-server"
            server_config = {"command": "test-command"}

            with (
                patch.object(component, "_get_mcp_server_config", return_value=server_config),
                patch.object(component, "update_build_config"),
            ):
                await component._update_tool_list(server_name)

                # Check update_tools was called correctly
                mock_update.assert_called_once()

                # Check tools were cached
                assert len(component.tools) == 2
                assert component._tool_cache == {"tool1": mock_tools[0], "tool2": mock_tools[1]}

    @pytest.mark.asyncio
    async def test_update_tool_list_sse(self, component):
        """Test updating tool list with SSE client."""
        mock_tools = [
            Mock(spec=StructuredTool, name="tool1", description="Tool 1"),
        ]

        with patch("lfx.components.agents.mcp_component.update_tools") as mock_update:
            mock_update.return_value = ("SSE", mock_tools, {"tool1": mock_tools[0]})

            server_name = "sse-server"
            server_config = {"url": "http://localhost:8080"}

            with (
                patch.object(component, "_get_mcp_server_config", return_value=server_config),
                patch.object(component, "update_build_config"),
            ):
                await component._update_tool_list(server_name)

                assert len(component.tools) == 1

    @pytest.mark.asyncio
    async def test_update_tool_list_empty_server(self, component):
        """Test updating tool list with empty server name."""
        with patch.object(component, "update_build_config") as mock_update_config:
            await component._update_tool_list("")

            # Should update config with empty options
            mock_update_config.assert_called()
            call_args = mock_update_config.call_args[0][0]
            assert call_args["tool"]["options"] == []

    @pytest.mark.asyncio
    async def test_get_mcp_server_config_from_cache(self, component):
        """Test getting MCP server config from cache."""
        server_name = "cached-server"
        cached_config = {"command": "cached-command"}

        with patch("lfx.components.agents.mcp_component.safe_cache_get") as mock_get:
            mock_get.return_value = {server_name: cached_config}

            config = await component._get_mcp_server_config(server_name)

            assert config == cached_config
            mock_get.assert_called_with(component._shared_component_cache, "servers")

    @pytest.mark.asyncio
    async def test_build_output_with_selected_tool(self, component):
        """Test build_output when a tool is selected."""
        # Set up component state
        component.tool = "test_tool"
        mock_tool = Mock(spec=StructuredTool)
        mock_tool.coroutine = AsyncMock(return_value="Tool result")
        component._tool_cache = {"test_tool": mock_tool}

        # Mock schema inputs
        component.schema_inputs = [
            {"name": "param1", "type": "str", "value": "value1"},
            {"name": "param2", "type": "int", "value": 42},
        ]

        with patch.object(component, "_validate_schema_inputs", return_value=component.schema_inputs):
            result = await component.build_output()

        # Check tool was called with correct arguments
        mock_tool.coroutine.assert_called_once_with(param1="value1", param2=42)

        # Check result is wrapped in Message
        assert isinstance(result, Message)
        assert result.text == "Tool result"

    @pytest.mark.asyncio
    async def test_build_output_no_tool_selected(self, component):
        """Test build_output when no tool is selected."""
        component.tool = ""

        result = await component.build_output()

        assert isinstance(result, Message)
        assert "No tool selected" in result.text

    @pytest.mark.asyncio
    async def test_build_output_tool_execution_error(self, component):
        """Test build_output when tool execution fails."""
        component.tool = "failing_tool"
        mock_tool = Mock(spec=StructuredTool)
        mock_tool.coroutine = AsyncMock(side_effect=Exception("Tool failed"))
        component._tool_cache = {"failing_tool": mock_tool}

        component.schema_inputs = []

        with patch.object(component, "_validate_schema_inputs", return_value=[]):
            result = await component.build_output()

        assert isinstance(result, Message)
        assert "Error executing tool" in result.text
        assert "Tool failed" in result.text

    def test_set_mcp_server(self, component):
        """Test set_mcp_server method."""
        server_name = "new-server"

        with (
            patch.object(component, "_update_tool_list"),
            patch("lfx.components.agents.mcp_component.safe_cache_set") as mock_set,
        ):
            component.set_mcp_server(server_name)

            # Should save to cache
            mock_set.assert_called_with(component._shared_component_cache, "last_selected_server", server_name)

            # Should trigger tool list update
            # Note: This is actually called via asyncio, so we can't easily test it here

    @pytest.mark.asyncio
    async def test_update_build_config_with_mcp_server(self, component):
        """Test update_build_config when build_config contains mcp_server."""
        # Mock getting saved server from cache
        saved_server = "saved-server"

        with patch("lfx.components.agents.mcp_component.safe_cache_get") as mock_get:
            mock_get.return_value = saved_server

            with patch.object(component, "_update_tool_list") as mock_update:
                build_config = {"mcp_server": {"value": ""}}

                await component.update_build_config(build_config, "mcp_server", "unused")

                # Should update the value from cache
                assert build_config["mcp_server"]["value"] == saved_server

                # Should trigger tool update
                mock_update.assert_called_once_with(saved_server)

    @pytest.mark.asyncio
    async def test_validate_schema_inputs_creates_inputs(self, component):
        """Test _validate_schema_inputs creates input fields from tool schema."""
        # Create a mock tool with schema
        mock_tool = Mock(spec=StructuredTool)
        mock_tool.args_schema = Mock()
        mock_tool.args_schema.model_json_schema.return_value = {
            "properties": {
                "input1": {
                    "type": "string",
                    "description": "First input",
                },
                "input2": {
                    "type": "integer",
                    "description": "Second input",
                    "default": 10,
                },
            },
            "required": ["input1"],
        }

        with patch("lfx.components.agents.mcp_component.schema_to_langflow_inputs") as mock_schema:
            mock_inputs = [
                {"name": "input1", "type": "str", "required": True},
                {"name": "input2", "type": "int", "required": False, "value": 10},
            ]
            mock_schema.return_value = mock_inputs

            result = await component._validate_schema_inputs(mock_tool)

            assert len(result) == 2
            assert result == mock_inputs

    def test_set_tool_mode(self, component):
        """Test set_tool_mode method."""
        # Should be true when a tool is selected
        component.tool = "some_tool"
        component.set_tool_mode()
        assert component.tool_mode is True

        # Should be false when no tool selected
        component.tool = ""
        component.set_tool_mode()
        assert component.tool_mode is False

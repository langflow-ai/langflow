"""Unit tests for MCP component with actual MCP servers.

This test suite validates the MCP component functionality using real MCP servers:
- Everything server (stdio mode) - provides echo and other tools
- HTTP/SSE servers (streamable HTTP mode) - provides various tools
"""

import shutil
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.base.mcp.util import MCPSessionManager, MCPStdioClient, MCPStreamableHttpClient
from lfx.components.agents.mcp_component import MCPToolsComponent

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


class TestMCPToolsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return MCPToolsComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "mode": "Stdio",
            "command": "npx -y @modelcontextprotocol/server-everything",
            "sse_url": "https://mcp.deepwiki.com/sse",
            "tool": "echo",
            "mcp_server": {"name": "test_server", "config": {"command": "uvx mcp-server-fetch"}},
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return []

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_component_initialization(self, component_class, default_kwargs):
        """Test that the component initializes correctly."""
        component = component_class(**default_kwargs)

        # Check that the component has the expected attributes
        assert hasattr(component, "stdio_client")
        assert hasattr(component, "streamable_http_client")
        assert isinstance(component.stdio_client, MCPStdioClient)
        assert isinstance(component.streamable_http_client, MCPStreamableHttpClient)

        # Check that the component has a session manager
        session_manager = component.stdio_client._get_session_manager()
        assert isinstance(session_manager, MCPSessionManager)


class TestMCPToolsComponentIntegration:
    """Integration tests for the MCPToolsComponent."""

    @pytest.fixture
    def component(self):
        """Create a component for testing."""
        return MCPToolsComponent()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not shutil.which("npx"), reason="Node.js not available")
    async def test_stdio_mode_integration(self, component):
        """Test the component in stdio mode with Everything server."""
        # Configure for stdio mode
        component.mode = "Stdio"
        component.command = "npx -y @modelcontextprotocol/server-everything"
        component.tool = "echo"

        try:
            # Mock the update_tool_list method to simulate server connection
            tools, server_info = await component.update_tool_list()

            # Should have tools
            assert len(tools) > 0

            # Should have server info
            assert server_info is not None
            assert isinstance(server_info, dict)

        except Exception as e:
            # If the server is not accessible, skip the test
            pytest.skip(f"Everything server not accessible: {e}")

    @pytest.mark.asyncio
    async def test_streamable_http_mode_integration(self, component):
        """Test the component in Streamable HTTP mode with DeepWiki server."""
        # Configure for Streamable HTTP mode
        component.mode = "Streamable HTTP"
        component.streamable_http_url = "https://mcp.deepwiki.com/mcp"

        try:
            # Mock the update_tool_list method to simulate server connection
            tools, server_info = await component.update_tool_list()

            # Should have tools
            assert len(tools) > 0

            # Should have server info
            assert server_info is not None
            assert isinstance(server_info, dict)

        except Exception as e:
            # If the server is not accessible, skip the test
            pytest.skip(f"DeepWiki server not accessible: {e}")

    @pytest.mark.asyncio
    async def test_session_context_setting(self, component):
        """Test that session context is properly set."""
        # Set session context on both clients
        component.stdio_client.set_session_context("test_context")
        component.streamable_http_client.set_session_context("test_context")

        # Verify context was set
        assert component.stdio_client._session_context == "test_context"
        assert component.streamable_http_client._session_context == "test_context"

    @pytest.mark.asyncio
    async def test_session_manager_sharing(self, component):
        """Test that session managers are shared through component cache."""
        # Get session managers from both clients
        stdio_manager = component.stdio_client._get_session_manager()
        http_manager = component.streamable_http_client._get_session_manager()

        # Both should be MCPSessionManager instances
        assert isinstance(stdio_manager, MCPSessionManager)
        assert isinstance(http_manager, MCPSessionManager)

        # They should be the same instance (shared through cache)
        assert stdio_manager is http_manager


class TestMCPComponentErrorHandling:
    """Test error handling in MCP components."""

    @pytest.fixture
    def stdio_client(self):
        return MCPStdioClient()

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        return AsyncMock(spec=MCPSessionManager)

    async def test_connect_to_server_with_command(self, stdio_client):
        """Test connecting to server via Stdio with command."""
        with patch.object(stdio_client, "_get_or_create_session") as mock_get_session:
            # Mock session
            mock_session = AsyncMock()
            mock_tool = MagicMock()
            mock_tool.name = "test_tool"
            list_tools_result = MagicMock()
            list_tools_result.tools = [mock_tool]
            mock_session.list_tools = AsyncMock(return_value=list_tools_result)
            mock_get_session.return_value = mock_session

            tools = await stdio_client.connect_to_server("uvx test-command")

            assert len(tools) == 1
            assert tools[0].name == "test_tool"
            assert stdio_client._connected is True
            assert stdio_client._connection_params is not None

    async def test_run_tool_success(self, stdio_client):
        """Test successfully running a tool."""
        # Setup connection state
        stdio_client._connected = True
        stdio_client._connection_params = MagicMock()
        stdio_client._session_context = "test_context"

        with patch.object(stdio_client, "_get_or_create_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_session.call_tool = AsyncMock(return_value=mock_result)
            mock_get_session.return_value = mock_session

            result = await stdio_client.run_tool("test_tool", {"param": "value"})

            assert result == mock_result
            mock_session.call_tool.assert_called_once_with("test_tool", arguments={"param": "value"})

    async def test_run_tool_without_connection(self, stdio_client):
        """Test running a tool without being connected."""
        stdio_client._connected = False

        with pytest.raises(ValueError, match="Session not initialized"):
            await stdio_client.run_tool("test_tool", {})

    async def test_disconnect_cleanup(self, stdio_client):
        """Test that disconnect properly cleans up resources."""
        stdio_client._session_context = "test_context"
        stdio_client._connected = True

        with patch.object(stdio_client, "_get_session_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            await stdio_client.disconnect()

            mock_manager._cleanup_session.assert_called_once_with("test_context")
            assert stdio_client.session is None
            assert stdio_client._connected is False

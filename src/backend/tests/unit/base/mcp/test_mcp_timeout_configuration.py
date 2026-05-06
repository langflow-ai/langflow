"""Tests for MCP timeout configuration feature.

This module tests the configurable timeout parameters added to support
long-running MCP tool executions (>30 seconds).

Related to customer issue TS021996258 (Verizon).
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from lfx.base.mcp.util import MCPStdioClient, MCPStreamableHttpClient, update_tools


class TestMCPTimeoutConfiguration:
    """Test timeout configuration at various levels."""

    @pytest.mark.asyncio
    async def test_stdio_client_default_timeout(self):
        """Test that MCPStdioClient uses global default timeout (180s)."""
        with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_setting:
            mock_get_setting.return_value = 180
            client = MCPStdioClient()
            assert client._tool_execution_timeout == 180
            mock_get_setting.assert_called_once_with("mcp_tool_execution_timeout", 180)

    @pytest.mark.asyncio
    async def test_stdio_client_custom_timeout(self):
        """Test that MCPStdioClient accepts custom timeout parameter."""
        client = MCPStdioClient(tool_execution_timeout=300)
        assert client._tool_execution_timeout == 300

    @pytest.mark.asyncio
    async def test_streamable_http_client_default_timeout(self):
        """Test that MCPStreamableHttpClient uses global default timeout (180s)."""
        with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_setting:
            mock_get_setting.return_value = 180
            client = MCPStreamableHttpClient()
            assert client._tool_execution_timeout == 180
            mock_get_setting.assert_called_once_with("mcp_tool_execution_timeout", 180)

    @pytest.mark.asyncio
    async def test_streamable_http_client_custom_timeout(self):
        """Test that MCPStreamableHttpClient accepts custom timeout parameter."""
        client = MCPStreamableHttpClient(tool_execution_timeout=300)
        assert client._tool_execution_timeout == 300

    @pytest.mark.asyncio
    async def test_stdio_run_tool_uses_client_timeout(self):
        """Test that run_tool uses client's configured timeout."""
        client = MCPStdioClient(tool_execution_timeout=120)
        client._connected = True
        client._connection_params = {"command": "test"}
        client._session_context = "test_context"

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value={"result": "success"})

        with (
            patch.object(client, "_get_or_create_session", return_value=mock_session),
            patch("asyncio.wait_for") as mock_wait_for,
        ):
            mock_wait_for.return_value = {"result": "success"}
            await client.run_tool("test_tool", {"arg": "value"})

            # Verify wait_for was called with client's timeout
            assert mock_wait_for.call_count == 1
            call_args = mock_wait_for.call_args
            assert call_args[1]["timeout"] == 120

    @pytest.mark.asyncio
    async def test_stdio_run_tool_timeout_override(self):
        """Test that run_tool accepts per-call timeout override."""
        client = MCPStdioClient(tool_execution_timeout=120)
        client._connected = True
        client._connection_params = {"command": "test"}
        client._session_context = "test_context"

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value={"result": "success"})

        with (
            patch.object(client, "_get_or_create_session", return_value=mock_session),
            patch("asyncio.wait_for") as mock_wait_for,
        ):
            mock_wait_for.return_value = {"result": "success"}
            # Override with 300 seconds
            await client.run_tool("test_tool", {"arg": "value"}, timeout=300)

            # Verify wait_for was called with override timeout
            assert mock_wait_for.call_count == 1
            call_args = mock_wait_for.call_args
            assert call_args[1]["timeout"] == 300

    @pytest.mark.asyncio
    async def test_streamable_http_run_tool_uses_client_timeout(self):
        """Test that StreamableHttpClient run_tool uses client's configured timeout."""
        client = MCPStreamableHttpClient(tool_execution_timeout=150)
        client._connected = True
        client._connection_params = {"url": "http://test"}
        client._session_context = "test_context"

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value={"result": "success"})

        with (
            patch.object(client, "_get_or_create_session", return_value=mock_session),
            patch("asyncio.wait_for") as mock_wait_for,
        ):
            mock_wait_for.return_value = {"result": "success"}
            await client.run_tool("test_tool", {"arg": "value"})

            # Verify wait_for was called with client's timeout
            assert mock_wait_for.call_count == 1
            call_args = mock_wait_for.call_args
            assert call_args[1]["timeout"] == 150

    @pytest.mark.asyncio
    async def test_streamable_http_run_tool_timeout_override(self):
        """Test that StreamableHttpClient run_tool accepts per-call timeout override."""
        client = MCPStreamableHttpClient(tool_execution_timeout=150)
        client._connected = True
        client._connection_params = {"url": "http://test"}
        client._session_context = "test_context"

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value={"result": "success"})

        with (
            patch.object(client, "_get_or_create_session", return_value=mock_session),
            patch("asyncio.wait_for") as mock_wait_for,
        ):
            mock_wait_for.return_value = {"result": "success"}
            # Override with 400 seconds
            await client.run_tool("test_tool", {"arg": "value"}, timeout=400)

            # Verify wait_for was called with override timeout
            assert mock_wait_for.call_count == 1
            call_args = mock_wait_for.call_args
            assert call_args[1]["timeout"] == 400

    @pytest.mark.asyncio
    async def test_update_tools_passes_timeout_to_stdio_client(self):
        """Test that update_tools passes timeout when creating MCPStdioClient."""
        server_config = {
            "mode": "Stdio",
            "command": "test-command",
            "args": [],
        }

        with patch("lfx.base.mcp.util.MCPStdioClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect_to_server = AsyncMock(return_value=[])
            mock_client._connected = True
            mock_client_class.return_value = mock_client

            await update_tools(
                server_name="test_server",
                server_config=server_config,
                tool_execution_timeout=250,
            )

            # Verify MCPStdioClient was created with timeout
            mock_client_class.assert_called_once_with(tool_execution_timeout=250)

    @pytest.mark.asyncio
    async def test_update_tools_passes_timeout_to_http_client(self):
        """Test that update_tools passes timeout when creating MCPStreamableHttpClient."""
        server_config = {
            "mode": "Streamable_HTTP",
            "url": "http://test-server",
        }

        with patch("lfx.base.mcp.util.MCPStreamableHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect_to_server = AsyncMock(return_value=[])
            mock_client._connected = True
            mock_client_class.return_value = mock_client

            await update_tools(
                server_name="test_server",
                server_config=server_config,
                tool_execution_timeout=350,
            )

            # Verify MCPStreamableHttpClient was created with timeout
            mock_client_class.assert_called_once_with(tool_execution_timeout=350)


class TestMCPTimeoutBehavior:
    """Test timeout behavior and error handling."""

    @pytest.mark.asyncio
    async def test_timeout_error_is_caught_and_retried(self):
        """Test that timeout errors trigger retry logic."""
        client = MCPStdioClient(tool_execution_timeout=1)
        client._connected = True
        client._connection_params = {"command": "test"}
        client._session_context = "test_context"

        mock_session = AsyncMock()
        # First call times out, second succeeds
        mock_session.call_tool = AsyncMock(side_effect=[asyncio.TimeoutError(), {"result": "success"}])

        with (
            patch.object(client, "_get_or_create_session", return_value=mock_session),
            patch("asyncio.wait_for") as mock_wait_for,
        ):
            # First call times out, second succeeds
            mock_wait_for.side_effect = [asyncio.TimeoutError(), {"result": "success"}]

            result = await client.run_tool("test_tool", {"arg": "value"})

            # Verify retry happened
            assert mock_wait_for.call_count == 2
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_zero_timeout_uses_global_default(self):
        """Test that timeout=0 or None falls back to global setting."""
        with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_setting:
            mock_get_setting.return_value = 180

            # Test with None
            client1 = MCPStdioClient(tool_execution_timeout=None)
            assert client1._tool_execution_timeout == 180

            # Test with 0 (should use provided 0, not fallback)
            client2 = MCPStdioClient(tool_execution_timeout=0)
            assert client2._tool_execution_timeout == 180  # 0 is falsy, so uses default


class TestMCPComponentTimeoutIntegration:
    """Test timeout integration with MCPToolsComponent."""

    def test_component_has_timeout_input(self):
        """Test that MCPToolsComponent has tool_execution_timeout input."""
        from lfx.components.models_and_agents.mcp_component import MCPToolsComponent

        # Check that the input exists
        input_names = [inp.name for inp in MCPToolsComponent.inputs]
        assert "tool_execution_timeout" in input_names

        # Find the timeout input
        timeout_input = next(inp for inp in MCPToolsComponent.inputs if inp.name == "tool_execution_timeout")

        # Verify it's an IntInput with correct defaults
        assert timeout_input.value == 0  # Default to global setting
        assert timeout_input.advanced is True  # Should be advanced setting

    def test_component_passes_timeout_to_clients(self):
        """Test that MCPToolsComponent reads timeout at execution time (not init time)."""
        from lfx.components.models_and_agents.mcp_component import MCPToolsComponent

        with (
            patch("lfx.components.models_and_agents.mcp_component.MCPStdioClient") as mock_stdio,
            patch("lfx.components.models_and_agents.mcp_component.MCPStreamableHttpClient") as mock_http,
        ):
            # Create component with custom timeout
            component = MCPToolsComponent(tool_execution_timeout=200.5)

            # Verify clients were created with None (timeout is read at execution time, not init time)
            # This matches the behavior of other settings like use_cache and headers
            mock_stdio.assert_called_once()
            call_kwargs = mock_stdio.call_args[1]
            assert call_kwargs.get("tool_execution_timeout") is None

            mock_http.assert_called_once()
            call_kwargs = mock_http.call_args[1]
            assert call_kwargs.get("tool_execution_timeout") is None

            # Verify the component has the timeout value stored for execution time
            assert component.tool_execution_timeout == 200.5

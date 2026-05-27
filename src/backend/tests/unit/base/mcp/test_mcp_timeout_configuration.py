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
            # Simulate: mcp_tool_execution_timeout=180, mcp_server_timeout=20
            def get_setting_side_effect(key, default):
                if key == "mcp_tool_execution_timeout":
                    return 180
                if key == "mcp_server_timeout":
                    return 20
                return default

            mock_get_setting.side_effect = get_setting_side_effect

            client = MCPStdioClient()
            assert client._tool_execution_timeout == 180

    @pytest.mark.asyncio
    async def test_stdio_client_custom_timeout(self):
        """Test that MCPStdioClient accepts custom timeout parameter."""
        client = MCPStdioClient(tool_execution_timeout=300)
        assert client._tool_execution_timeout == 300

    @pytest.mark.asyncio
    async def test_streamable_http_client_default_timeout(self):
        """Test that MCPStreamableHttpClient uses global default timeout (180s)."""
        with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_setting:
            # Simulate: mcp_tool_execution_timeout=180, mcp_server_timeout=20
            def get_setting_side_effect(key, default):
                if key == "mcp_tool_execution_timeout":
                    return 180
                if key == "mcp_server_timeout":
                    return 20
                return default

            mock_get_setting.side_effect = get_setting_side_effect

            client = MCPStreamableHttpClient()
            assert client._tool_execution_timeout == 180

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
            # Simulate: mcp_tool_execution_timeout=180, mcp_server_timeout=20
            def get_setting_side_effect(key, default):
                if key == "mcp_tool_execution_timeout":
                    return 180
                if key == "mcp_server_timeout":
                    return 20
                return default

            mock_get_setting.side_effect = get_setting_side_effect

            # Test with None - should fall back to global setting
            client1 = MCPStdioClient(tool_execution_timeout=None)
            assert client1._tool_execution_timeout == 180

            # Test with 0 - should fall back to global setting since 0 is an invalid explicit timeout
            client2 = MCPStdioClient(tool_execution_timeout=0)
            assert client2._tool_execution_timeout == 180

    @pytest.mark.asyncio
    async def test_multiple_clients_independent_timeouts(self):
        """Test that multiple client instances maintain independent timeout values."""
        # Create multiple clients with different timeout values
        client1 = MCPStdioClient(tool_execution_timeout=100)
        client2 = MCPStdioClient(tool_execution_timeout=200)
        client3 = MCPStreamableHttpClient(tool_execution_timeout=300)
        client4 = MCPStreamableHttpClient(tool_execution_timeout=400)

        # Verify each client maintains its own timeout value
        assert client1._tool_execution_timeout == 100
        assert client2._tool_execution_timeout == 200
        assert client3._tool_execution_timeout == 300
        assert client4._tool_execution_timeout == 400

        # Verify changing one doesn't affect others
        client1._tool_execution_timeout = 150
        assert client1._tool_execution_timeout == 150
        assert client2._tool_execution_timeout == 200  # Unchanged
        assert client3._tool_execution_timeout == 300  # Unchanged
        assert client4._tool_execution_timeout == 400  # Unchanged

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_independent_timeout_overrides(self):
        """Test that multiple tool calls with different timeout overrides remain independent."""
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

            # Call multiple tools with different timeout overrides
            await client.run_tool("tool1", {"arg": "value1"}, timeout=100)
            await client.run_tool("tool2", {"arg": "value2"}, timeout=200)
            await client.run_tool("tool3", {"arg": "value3"}, timeout=300)
            await client.run_tool("tool4", {"arg": "value4"})  # Uses client default (120)

            # Verify each call used its own timeout
            assert mock_wait_for.call_count == 4

            # Check each call's timeout parameter
            call_timeouts = [call[1]["timeout"] for call in mock_wait_for.call_args_list]
            assert call_timeouts == [100, 200, 300, 120]

    @pytest.mark.asyncio
    async def test_none_timeout_preserves_existing_client_timeout(self):
        """Test that passing None as timeout preserves existing client's timeout."""
        from lfx.base.mcp.util import update_tools

        # Create a client with a specific timeout
        initial_client = MCPStdioClient(tool_execution_timeout=250)

        server_config = {
            "mode": "Stdio",
            "command": "test-command",
            "args": [],
        }

        with patch.object(initial_client, "connect_to_server", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = []
            initial_client._connected = True

            # Call update_tools with None timeout - should preserve existing 250s
            await update_tools(
                server_name="test_server",
                server_config=server_config,
                tool_execution_timeout=None,
                mcp_stdio_client=initial_client,
            )

            # Verify the client's timeout was NOT overwritten
            assert initial_client._tool_execution_timeout == 250

    @pytest.mark.asyncio
    async def test_mcp_sse_client_receives_timeout(self):
        """Test that mcp_sse_client (backward compatibility alias) receives timeout."""
        from lfx.base.mcp.util import update_tools

        # Create an SSE client (which is actually a StreamableHttpClient)
        sse_client = MCPStreamableHttpClient(tool_execution_timeout=100)

        server_config = {
            "mode": "Streamable_HTTP",
            "url": "http://test-server",
        }

        with patch.object(sse_client, "connect_to_server", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = []
            sse_client._connected = True

            # Call update_tools with mcp_sse_client and a new timeout
            await update_tools(
                server_name="test_server",
                server_config=server_config,
                tool_execution_timeout=350,
                mcp_sse_client=sse_client,
            )

            # Verify the SSE client received the new timeout
            assert sse_client._tool_execution_timeout == 350


class TestMCPTimeoutSettingsValidation:
    """Test MCP timeout validation that belongs with backend settings coverage."""

    @pytest.mark.asyncio
    async def test_global_setting_validation_rejects_zero(self):
        """Test that global mcp_tool_execution_timeout setting rejects zero values."""
        from lfx.services.settings.base import Settings

        # Test the validator directly
        with pytest.raises(ValueError, match="mcp_tool_execution_timeout must be greater than 0"):
            Settings.validate_mcp_tool_execution_timeout(0.0)

    @pytest.mark.asyncio
    async def test_global_setting_validation_rejects_negative(self):
        """Test that global mcp_tool_execution_timeout setting rejects negative values."""
        from lfx.services.settings.base import Settings

        # Test the validator directly
        with pytest.raises(ValueError, match="mcp_tool_execution_timeout must be greater than 0"):
            Settings.validate_mcp_tool_execution_timeout(-100.0)

    @pytest.mark.asyncio
    async def test_global_setting_accepts_positive_float(self):
        """Test that global mcp_tool_execution_timeout setting accepts positive float values."""
        from lfx.services.settings.base import Settings

        # Test that the validator accepts positive values
        # Note: We test the validator logic, not the full Settings initialization
        validated_value = Settings.validate_mcp_tool_execution_timeout(180.0)
        assert validated_value == 180.0

        validated_value = Settings.validate_mcp_tool_execution_timeout(250.5)
        assert validated_value == 250.5

        validated_value = Settings.validate_mcp_tool_execution_timeout(0.5)
        assert validated_value == 0.5

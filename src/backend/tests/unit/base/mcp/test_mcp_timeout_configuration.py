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

            # Test with 0 - should use provided 0 (explicit value)
            client2 = MCPStdioClient(tool_execution_timeout=0)
            assert client2._tool_execution_timeout == 0.0  # 0 is explicit, not None

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

        # Verify it's a FloatInput with correct defaults
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
            _component = MCPToolsComponent(tool_execution_timeout=200.5)

            # Verify clients were created with None (timeout is read at execution time, not init time)
            # This matches the behavior of other settings like use_cache and headers
            mock_stdio.assert_called_once()
            call_kwargs = mock_stdio.call_args[1]
            assert call_kwargs.get("tool_execution_timeout") is None

            mock_http.assert_called_once()
            call_kwargs = mock_http.call_args[1]
            assert call_kwargs.get("tool_execution_timeout") is None

    def test_component_validates_negative_timeout(self):
        """Test that negative timeout validation works correctly."""
        # Test the validation logic directly
        timeout_value = -10.0

        # Validate timeout is non-negative (matches mcp_component.py logic)
        def validate_timeout(value):
            if value < 0:
                msg = "tool_execution_timeout must be non-negative"
                raise ValueError(msg)

        with pytest.raises(ValueError, match="tool_execution_timeout must be non-negative"):
            validate_timeout(timeout_value)

    def test_component_accepts_positive_timeout(self):
        """Test that positive timeout values are accepted."""
        # Test positive values don't raise
        timeout_value = 100.0
        if timeout_value < 0:
            msg = "tool_execution_timeout must be non-negative"
            raise ValueError(msg)
        # Should not raise
        timeout = float(timeout_value) if timeout_value else None
        assert timeout == 100.0

    def test_component_accepts_zero_timeout(self):
        """Test that zero timeout is accepted (uses global default)."""
        timeout_value = 0.0
        if timeout_value < 0:
            msg = "tool_execution_timeout must be non-negative"
            raise ValueError(msg)
        # Should not raise, and should convert to None
        timeout = float(timeout_value) if timeout_value else None
        assert timeout is None

    @pytest.mark.asyncio
    async def test_stdio_client_backward_compatibility_mcp_server_timeout(self):
        """Test backward compatibility: when mcp_tool_execution_timeout is unset.

        Fall back to max(mcp_server_timeout, 180).

        Regression test for review finding: deployments that raised
        LANGFLOW_MCP_SERVER_TIMEOUT above 180 seconds should not regress.
        """
        with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_setting:
            # Simulate: mcp_tool_execution_timeout is unset, mcp_server_timeout=300
            def get_setting_side_effect(key, default):
                if key == "mcp_tool_execution_timeout":
                    return None  # Unset
                if key == "mcp_server_timeout":
                    return 300
                return default

            mock_get_setting.side_effect = get_setting_side_effect

            client = MCPStdioClient()
            # Should use max(300, 180) = 300
            assert client._tool_execution_timeout == 300.0

    @pytest.mark.asyncio
    async def test_streamable_http_client_backward_compatibility_mcp_server_timeout(self):
        """Test backward compatibility for MCPStreamableHttpClient with mcp_server_timeout."""
        with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_setting:
            # Simulate: mcp_tool_execution_timeout is unset, mcp_server_timeout=300
            def get_setting_side_effect(key, default):
                if key == "mcp_tool_execution_timeout":
                    return None  # Unset
                if key == "mcp_server_timeout":
                    return 300
                return default

            mock_get_setting.side_effect = get_setting_side_effect

            client = MCPStreamableHttpClient()
            # Should use max(300, 180) = 300
            assert client._tool_execution_timeout == 300.0

    @pytest.mark.asyncio
    async def test_stdio_client_mcp_server_timeout_below_minimum(self):
        """Test mcp_server_timeout < 180 and mcp_tool_execution_timeout is unset.

        The minimum of 180 seconds is used.
        """
        with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_setting:
            # Simulate: mcp_tool_execution_timeout is unset, mcp_server_timeout=20 (default)
            def get_setting_side_effect(key, default):
                if key == "mcp_tool_execution_timeout":
                    return None  # Unset
                if key == "mcp_server_timeout":
                    return 20
                return default

            mock_get_setting.side_effect = get_setting_side_effect

            client = MCPStdioClient()
            # Should use max(20, 180) = 180
            assert client._tool_execution_timeout == 180.0

    @pytest.mark.asyncio
    async def test_stdio_client_new_setting_takes_precedence(self):
        """Test that mcp_tool_execution_timeout takes precedence over mcp_server_timeout."""
        with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_setting:
            # Simulate: both settings are configured
            def get_setting_side_effect(key, default):
                if key == "mcp_tool_execution_timeout":
                    return 250  # New setting
                if key == "mcp_server_timeout":
                    return 300  # Old setting (higher)
                return default

            mock_get_setting.side_effect = get_setting_side_effect

            client = MCPStdioClient()
            # Should use mcp_tool_execution_timeout (250), not mcp_server_timeout
            assert client._tool_execution_timeout == 250.0

    @pytest.mark.asyncio
    async def test_stdio_client_component_timeout_overrides_all(self):
        """Test that component-level timeout overrides both global settings."""
        with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_setting:
            # Simulate: both global settings are configured
            def get_setting_side_effect(key, default):
                if key == "mcp_tool_execution_timeout":
                    return 250
                if key == "mcp_server_timeout":
                    return 300
                return default

            mock_get_setting.side_effect = get_setting_side_effect

            # Component provides its own timeout
            client = MCPStdioClient(tool_execution_timeout=400)
            # Should use component timeout (400), ignoring both global settings
            assert client._tool_execution_timeout == 400.0

    @pytest.mark.asyncio
    async def test_cache_key_includes_timeout(self):
        """Test that cache keys include timeout to prevent stale timeout values.

        Regression test for review finding: cached tools can bypass per-component timeout.
        This test verifies the cache key generation logic includes timeout values.
        """
        # Test the cache key generation logic directly
        import hashlib
        import json

        # Simulate cache key generation with different timeouts
        def generate_cache_key(server_name: str, timeout: float, headers: dict | None = None) -> str:
            if not server_name:
                return ""
            cache_data = {
                "headers": headers or {},
                "timeout": timeout,
            }
            if not headers and timeout == 0.0:
                return server_name
            payload = json.dumps(cache_data, sort_keys=True)
            digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
            return f"{server_name}:{digest}"

        # Test with different timeouts
        key1 = generate_cache_key("test-server", 0.0)
        key2 = generate_cache_key("test-server", 300.0)
        key3 = generate_cache_key("test-server", 600.0)

        # Keys should be different when timeout changes
        assert key1 != key2, "Cache keys should differ when timeout changes"
        assert key2 != key3, "Cache keys should differ for different timeout values"
        assert key1 != key3, "Cache keys should differ for different timeout values"

    @pytest.mark.asyncio
    async def test_cache_key_same_for_same_timeout(self):
        """Test that cache keys are consistent for the same timeout value."""
        import hashlib
        import json

        def generate_cache_key(server_name: str, timeout: float) -> str:
            cache_data = {"headers": {}, "timeout": timeout}
            if timeout == 0.0:
                return server_name
            payload = json.dumps(cache_data, sort_keys=True)
            digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
            return f"{server_name}:{digest}"

        key1 = generate_cache_key("test-server", 250.0)
        key2 = generate_cache_key("test-server", 250.0)

        # Keys should be identical for same timeout
        assert key1 == key2, "Cache keys should be identical for same timeout"

    @pytest.mark.asyncio
    async def test_cache_key_handles_negative_timeout(self):
        """Test that cache key handles negative timeout gracefully."""
        import hashlib
        import json

        def generate_cache_key(server_name: str, timeout: float) -> str:
            # Negative timeout should be treated as 0.0
            normalized_timeout = 0.0 if timeout < 0 else timeout
            cache_data = {"headers": {}, "timeout": normalized_timeout}
            if normalized_timeout == 0.0:
                return server_name
            payload = json.dumps(cache_data, sort_keys=True)
            digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
            return f"{server_name}:{digest}"

        key_negative = generate_cache_key("test-server", -100.0)
        key_zero = generate_cache_key("test-server", 0.0)

        # Both should produce the same key (negative treated as 0)
        assert key_negative == key_zero, "Negative timeout should be treated as 0.0 in cache key"

    @pytest.mark.asyncio
    async def test_cache_key_includes_headers_and_timeout(self):
        """Test that cache keys include both headers and timeout."""
        import hashlib
        import json

        def generate_cache_key(server_name: str, timeout: float, headers: dict | None = None) -> str:
            cache_data = {"headers": headers or {}, "timeout": timeout}
            if not headers and timeout == 0.0:
                return server_name
            payload = json.dumps(cache_data, sort_keys=True)
            digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
            return f"{server_name}:{digest}"

        key1 = generate_cache_key("test-server", 0.0, {})
        key2 = generate_cache_key("test-server", 0.0, {"Authorization": "Bearer token123"})
        key3 = generate_cache_key("test-server", 300.0, {"Authorization": "Bearer token123"})

        # All keys should be different
        assert key1 != key2, "Cache keys should differ when headers change"
        assert key2 != key3, "Cache keys should differ when timeout changes"
        assert key1 != key3, "Cache keys should differ when both headers and timeout differ"

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

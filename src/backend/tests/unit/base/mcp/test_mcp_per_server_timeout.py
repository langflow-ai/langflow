"""Tests for per-server startup timeout in MCP stdio connections.

Why this exists: some MCP servers we ship as defaults (notably
`@wonderwhy-er/desktop-commander` via `npx -y`) take 30-90s on the very first
launch because npm has to download the package + dependencies. The global
`mcp_server_timeout` (default 20s) is too tight for first-run, but we don't
want to raise it globally — that would degrade UX for legitimate failures.

The fix: `MCPStdioClient.connect_to_server` accepts an optional `timeout=`
override; `update_tools` reads `server_config["metadata"]["startup_timeout_seconds"]`
and passes it. Default-server registry entries can opt in via a spec field.

This file covers the wiring; the registry side lives in
`tests/unit/api/utils/mcp/test_default_servers_registry.py`.
"""

from unittest.mock import AsyncMock, patch

import pytest
from lfx.base.mcp.util import MCPStdioClient, update_tools


class TestMcpStdioClientAcceptsCustomTimeout:
    async def test_should_use_custom_timeout_when_provided(self):
        """Slice E1: explicit timeout= overrides the global setting."""
        client = MCPStdioClient()

        captured: dict[str, float | None] = {"timeout": None}

        async def _capturing_wait_for(coro, *, timeout):
            captured["timeout"] = timeout
            # Drain the coroutine so we don't leak a warning.
            coro.close()
            return []

        with (
            patch("lfx.base.mcp.util.asyncio.wait_for", new=_capturing_wait_for),
            patch.object(client, "_connect_to_server", new=AsyncMock(return_value=[])),
        ):
            await client.connect_to_server("echo hi", timeout=2.5)

        assert captured["timeout"] == pytest.approx(2.5)

    async def test_should_fall_back_to_global_when_timeout_none(self):
        """Slice E3 / regression: omitting timeout preserves the historical default."""
        from lfx.services.deps import get_settings_service

        client = MCPStdioClient()
        global_timeout = float(get_settings_service().settings.mcp_server_timeout)

        captured: dict[str, float | None] = {"timeout": None}

        async def _capturing_wait_for(coro, *, timeout):
            captured["timeout"] = timeout
            coro.close()
            return []

        with (
            patch("lfx.base.mcp.util.asyncio.wait_for", new=_capturing_wait_for),
            patch.object(client, "_connect_to_server", new=AsyncMock(return_value=[])),
        ):
            await client.connect_to_server("echo hi")

        assert captured["timeout"] == pytest.approx(global_timeout)


class TestUpdateToolsPropagatesPerServerTimeout:
    async def test_should_pass_metadata_startup_timeout_to_connect(self):
        """Slice E2: the orchestrator stamps timeout in metadata; update_tools forwards it."""
        mock_stdio = AsyncMock(spec=MCPStdioClient)
        mock_stdio.connect_to_server.return_value = []
        mock_stdio._connected = True

        server_config = {
            "command": "npx",
            "args": ["-y", "@wonderwhy-er/desktop-commander@latest"],
            "env": {},
            "metadata": {"startup_timeout_seconds": 60},
        }

        await update_tools("test-server", server_config, mcp_stdio_client=mock_stdio)

        # connect_to_server should have been called with timeout=60 (kwarg).
        kwargs = mock_stdio.connect_to_server.call_args.kwargs
        assert kwargs.get("timeout") == 60

    async def test_should_omit_timeout_when_metadata_field_absent(self):
        """Slice E3: legacy server configs without metadata stay on the global default."""
        mock_stdio = AsyncMock(spec=MCPStdioClient)
        mock_stdio.connect_to_server.return_value = []
        mock_stdio._connected = True

        server_config = {
            "command": "uvx",
            "args": ["mcp-proxy", "http://localhost:7860/api/v1/mcp/sse"],
            "env": {},
        }

        await update_tools("legacy-server", server_config, mcp_stdio_client=mock_stdio)

        kwargs = mock_stdio.connect_to_server.call_args.kwargs
        # Either omitted entirely or explicitly None — both mean "fall back to global".
        assert kwargs.get("timeout") is None

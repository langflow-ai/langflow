from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.base.mcp.util import (
    MCPSessionManager,
    MCPStdioClient,
    MCPStreamableHttpClient,
    _resolve_mcp_tool_execution_timeout,
    get_session_validation_timeout,
)


def test_resolve_mcp_tool_execution_timeout_uses_explicit_value():
    assert _resolve_mcp_tool_execution_timeout(42) == 42.0


def test_resolve_mcp_tool_execution_timeout_uses_max_of_global_settings():
    with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_mcp_setting:
        mock_get_mcp_setting.side_effect = lambda key, default=None: {
            "mcp_tool_execution_timeout": 120.0,
            "mcp_server_timeout": 240,
        }.get(key, default)

        assert _resolve_mcp_tool_execution_timeout(None) == 240.0


def test_resolve_mcp_tool_execution_timeout_uses_tool_timeout_when_larger():
    with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_mcp_setting:
        mock_get_mcp_setting.side_effect = lambda key, default=None: {
            "mcp_tool_execution_timeout": 300.0,
            "mcp_server_timeout": 20,
        }.get(key, default)

        assert _resolve_mcp_tool_execution_timeout(None) == 300.0


def test_resolve_mcp_tool_execution_timeout_uses_server_timeout_when_tool_timeout_is_missing():
    with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_mcp_setting:
        mock_get_mcp_setting.side_effect = lambda key, default=None: {
            "mcp_tool_execution_timeout": None,
            "mcp_server_timeout": 240,
        }.get(key, default)

        assert _resolve_mcp_tool_execution_timeout(None) == 240.0


def test_resolve_mcp_tool_execution_timeout_uses_server_timeout_when_tool_timeout_is_not_set():
    with patch("lfx.base.mcp.util._get_mcp_setting") as mock_get_mcp_setting:
        mock_get_mcp_setting.side_effect = lambda key, default=None: {
            "mcp_server_timeout": 210,
        }.get(key, default)

        assert _resolve_mcp_tool_execution_timeout(None) == 210.0


def test_resolve_mcp_tool_execution_timeout_falls_back_to_180_when_no_settings_exist():
    with patch("lfx.base.mcp.util._get_mcp_setting", return_value=None):
        assert _resolve_mcp_tool_execution_timeout(None) == 180.0


@pytest.mark.parametrize(
    ("server_timeout", "expected"),
    [
        (None, 10.0),
        (20, 10.0),
        (60, 20.0),
    ],
)
def test_get_session_validation_timeout_uses_connection_budget(server_timeout, expected):
    with patch("lfx.base.mcp.util._get_mcp_setting", return_value=server_timeout):
        assert get_session_validation_timeout() == expected


@pytest.mark.asyncio
async def test_session_connectivity_validation_uses_resolved_timeout():
    manager = MCPSessionManager()
    session = AsyncMock()
    session.list_tools.return_value = SimpleNamespace(tools=[])
    observed_timeout = None

    async def wait_for(awaitable, *, timeout):
        nonlocal observed_timeout
        observed_timeout = timeout
        return await awaitable

    try:
        with (
            patch("lfx.base.mcp.util.get_session_validation_timeout", return_value=20.0),
            patch("lfx.base.mcp.util.asyncio.wait_for", side_effect=wait_for),
        ):
            assert await manager._validate_session_connectivity(session) is True
    finally:
        await manager.cleanup_all()

    assert observed_timeout == 20.0


def test_mcp_stdio_client_uses_resolved_timeout():
    with patch("lfx.base.mcp.util._resolve_mcp_tool_execution_timeout", return_value=240.0):
        client = MCPStdioClient(tool_execution_timeout=None)

    assert client._tool_execution_timeout == 240.0


def test_mcp_streamable_http_client_uses_resolved_timeout():
    with patch("lfx.base.mcp.util._resolve_mcp_tool_execution_timeout", return_value=240.0):
        client = MCPStreamableHttpClient(tool_execution_timeout=None)

    assert client._tool_execution_timeout == 240.0


# Made with Bob

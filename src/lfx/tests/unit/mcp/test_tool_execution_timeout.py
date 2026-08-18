from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.base.mcp.util import (
    MCPStdioClient,
    MCPStreamableHttpClient,
    _resolve_mcp_tool_execution_timeout,
)
from lfx.observability import _root_error_type


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


def test_mcp_stdio_client_uses_resolved_timeout():
    with patch("lfx.base.mcp.util._resolve_mcp_tool_execution_timeout", return_value=240.0):
        client = MCPStdioClient(tool_execution_timeout=None)

    assert client._tool_execution_timeout == 240.0


def test_mcp_streamable_http_client_uses_resolved_timeout():
    with patch("lfx.base.mcp.util._resolve_mcp_tool_execution_timeout", return_value=240.0):
        client = MCPStreamableHttpClient(tool_execution_timeout=None)

    assert client._tool_execution_timeout == 240.0


@pytest.mark.parametrize(
    ("client_class", "connection_params"),
    [
        (MCPStdioClient, SimpleNamespace(command="python", args=["server.py"])),
        (MCPStreamableHttpClient, {"url": "http://127.0.0.1:9931/mcp"}),
    ],
)
@pytest.mark.asyncio
async def test_repeated_tool_timeout_preserves_the_root_error(client_class, connection_params):
    client = client_class(tool_execution_timeout=0.01)
    client._connected = True
    client._connection_params = connection_params
    session = AsyncMock()
    session.call_tool.side_effect = TimeoutError

    with (
        patch.object(client, "_get_or_create_session", new=AsyncMock(return_value=session)),
        patch("lfx.base.mcp.util.asyncio.sleep", new=AsyncMock()),
        pytest.raises(ValueError, match="Maximum retries exceeded") as exc_info,
    ):
        await client._run_tool("slow", {})

    assert isinstance(exc_info.value.__cause__, TimeoutError)
    assert _root_error_type(exc_info.value) == "TimeoutError"


# Made with Bob

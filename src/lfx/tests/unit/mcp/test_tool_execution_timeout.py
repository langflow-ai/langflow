import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.base.mcp.util import (
    ClosedResourceError,
    MCPSessionManager,
    MCPStdioClient,
    MCPStreamableHttpClient,
    _resolve_mcp_tool_execution_timeout,
    get_session_init_timeout,
    get_session_validation_timeout,
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


CLIENTS = pytest.mark.parametrize(
    ("client_class", "connection_params"),
    [
        (MCPStdioClient, SimpleNamespace(command="python", args=["server.py"])),
        (MCPStreamableHttpClient, {"url": "http://127.0.0.1:9931/mcp"}),
    ],
)


class _SideEffectSession:
    """Runs the tool's side effect at once, then answers the first call late."""

    def __init__(self, first_response_delay: float) -> None:
        self.calls = 0
        self._first_response_delay = first_response_delay

    async def call_tool(self, name: str, arguments: dict) -> SimpleNamespace:
        del name, arguments
        self.calls += 1
        if self.calls == 1:
            await asyncio.sleep(self._first_response_delay)
        return SimpleNamespace(content=[], isError=False)


@CLIENTS
@pytest.mark.asyncio
async def test_tool_timeout_preserves_the_root_error(client_class, connection_params):
    client = client_class(tool_execution_timeout=0.01)
    client._connected = True
    client._connection_params = connection_params
    session = AsyncMock()
    session.call_tool.side_effect = TimeoutError

    with (
        patch.object(client, "_get_or_create_session", new=AsyncMock(return_value=session)),
        patch("lfx.base.mcp.util.asyncio.sleep", new=AsyncMock()),
        pytest.raises(ValueError, match="timed out") as exc_info,
    ):
        await client._run_tool("slow", {})

    assert isinstance(exc_info.value.__cause__, TimeoutError)
    assert _root_error_type(exc_info.value) == "TimeoutError"


@CLIENTS
@pytest.mark.asyncio
async def test_should_run_tool_once_when_response_times_out(client_class, connection_params):
    client = client_class(tool_execution_timeout=0.01)
    client._connected = True
    client._connection_params = connection_params
    session = _SideEffectSession(first_response_delay=0.2)

    with (
        patch.object(client, "_get_or_create_session", new=AsyncMock(return_value=session)),
        pytest.raises(ValueError, match="create_record") as exc_info,
    ):
        await client._run_tool("create_record", {"value": "payment-1"})

    assert session.calls == 1
    assert "not retried" in str(exc_info.value)
    # Python 3.10's wait_for raises asyncio.TimeoutError, not yet the builtin.
    assert isinstance(exc_info.value.__cause__, asyncio.TimeoutError | TimeoutError)


@CLIENTS
@pytest.mark.asyncio
async def test_should_still_retry_when_session_closed_before_the_call(client_class, connection_params):
    client = client_class(tool_execution_timeout=1)
    client._connected = True
    client._connection_params = connection_params
    client._session_context = "ctx"
    result = SimpleNamespace(content=[], isError=False)
    session = AsyncMock()
    session.call_tool.side_effect = [ClosedResourceError(), result]
    # A real manager would start its cleanup loop, which spins forever on the
    # patched sleep below.
    manager = MagicMock(_cleanup_session=AsyncMock(), discard_session=AsyncMock())

    with (
        patch.object(client, "_get_or_create_session", new=AsyncMock(return_value=session)),
        patch.object(client, "_get_session_manager", return_value=manager),
        patch("lfx.base.mcp.util.asyncio.sleep", new=AsyncMock()),
    ):
        assert await client._run_tool("create_record", {}) is result

    assert session.call_tool.await_count == 2
    assert manager.discard_session.await_args.args[1] is session


@pytest.mark.parametrize(
    ("server_timeout", "expected"),
    [
        (None, 60.0),
        (0, 60.0),
        (-1, 60.0),
        (20, 20.0),
        (60, 60.0),
        (120, 120.0),
    ],
)
def test_get_session_init_timeout_uses_connection_budget(server_timeout, expected):
    """The session readiness wait must follow mcp_server_timeout, not a hardcoded 30 s.

    Missing or non-positive values fall back to the settings default rather than a shorter cap.
    """
    with patch("lfx.base.mcp.util._get_mcp_setting", return_value=server_timeout):
        assert get_session_init_timeout() == expected


class _ReadyClientSession:
    """ClientSession stand-in whose initialize completes immediately."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def initialize(self):
        return None


_real_wait_for = asyncio.wait_for


def _recording_wait_for(observed: list[float]):
    """Record every timeout handed to asyncio.wait_for while still enforcing it."""

    async def wait_for(awaitable, *, timeout):
        observed.append(timeout)
        return await _real_wait_for(awaitable, timeout=timeout)

    return wait_for


@pytest.mark.asyncio
async def test_stdio_session_creation_waits_with_configured_budget():
    """LE-2507: a raised LANGFLOW_MCP_SERVER_TIMEOUT must reach the stdio readiness wait."""
    manager = MCPSessionManager()
    observed: list[float] = []
    stdio_client = MagicMock()
    stdio_client.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    stdio_client.return_value.__aexit__ = AsyncMock(return_value=None)

    task = None
    try:
        with (
            patch("lfx.base.mcp.util.get_session_init_timeout", return_value=45.0),
            patch("lfx.base.mcp.util.ClientSession", return_value=_ReadyClientSession()),
            patch("mcp.client.stdio.stdio_client", stdio_client),
            patch("lfx.base.mcp.util.asyncio.wait_for", side_effect=_recording_wait_for(observed)),
        ):
            _session, task = await manager._create_stdio_session("test_session", MagicMock())
    finally:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await manager.cleanup_all()

    # The patch is process-wide for the block, so assert on presence rather than exact shape.
    assert 45.0 in observed
    assert 30.0 not in observed


@pytest.mark.asyncio
async def test_streamable_http_session_creation_waits_with_configured_budget():
    """LE-2507: the same budget must reach the Streamable HTTP readiness wait."""
    manager = MCPSessionManager()
    observed: list[float] = []
    http_client = MagicMock()
    http_client.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    http_client.return_value.__aexit__ = AsyncMock(return_value=None)
    connection_params = {"url": "http://127.0.0.1:9931/mcp", "headers": {}, "timeout_seconds": 5}

    task = None
    try:
        with (
            patch("lfx.base.mcp.util.get_session_init_timeout", return_value=45.0),
            patch("lfx.base.mcp.util.ClientSession", return_value=_ReadyClientSession()),
            patch("mcp.client.streamable_http.streamablehttp_client", http_client),
            patch("lfx.base.mcp.util.asyncio.wait_for", side_effect=_recording_wait_for(observed)),
        ):
            _session, task, transport, _locked = await manager._create_streamable_http_session(
                "test_session", connection_params
            )
    finally:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await manager.cleanup_all()

    assert transport == "streamable_http"
    # The background task also bounds session.initialize() (2 s); the readiness wait is the budget.
    assert 45.0 in observed
    assert 30.0 not in observed


# Made with Bob


@CLIENTS
@pytest.mark.asyncio
async def test_should_keep_client_usable_when_a_tool_call_times_out(client_class, connection_params):
    client = client_class(tool_execution_timeout=0.01)
    client._connected = True
    client._connection_params = connection_params
    session = _SideEffectSession(first_response_delay=0.2)

    with patch.object(client, "_get_or_create_session", new=AsyncMock(return_value=session)):
        with pytest.raises(ValueError, match="timed out"):
            await client._run_tool("create_record", {"value": "payment-1"})
        result = await client._run_tool("create_record", {"value": "payment-2"})

    assert result.isError is False
    assert session.calls == 2

"""Transport-level support the pinned MCP mode needs from ``lfx.base.mcp.util``.

Three additive behaviors, all no-ops for the existing discovery path:

* the ``InitializeResult`` is retained on the session, so ``serverInfo`` can be
  compared against a pin (the SDK otherwise drops it),
* each tool carries its raw ``inputSchema``/``outputSchema`` on ``metadata``,
  because ``create_input_schema_from_json_schema`` is lossy and a pin compares
  raw JSON Schema, and
* ``allow_sse_fallback=False`` in a server config pins the transport: the SSE
  fallback is not attempted, so a pinned endpoint answering only on a transport
  the pin does not name surfaces as a failure instead of a silent downgrade.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.base.mcp.util import (
    MCPSessionManager,
    MCPStreamableHttpClient,
    server_info_from_session,
    update_tools,
)

CONNECTION_PARAMS = {
    "url": "http://mcp.test.invalid/mcp",
    "headers": {},
    "timeout_seconds": 5,
    "verify_ssl": True,
}


class _FakeSession:
    """Stands in for ``mcp.ClientSession``; records what ``initialize`` returned."""

    def __init__(self, initialize_result):
        self._initialize_result = initialize_result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def initialize(self):
        return self._initialize_result


def _transport_client():
    client = MagicMock()
    client.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    client.return_value.__aexit__ = AsyncMock(return_value=None)
    return client


async def _shutdown(manager: MCPSessionManager, task) -> None:
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    manager._background_tasks.discard(task)


@pytest.fixture
def manager() -> MCPSessionManager:
    return MCPSessionManager()


async def test_server_info_is_retained_from_the_streamable_http_handshake(manager):
    initialize_result = SimpleNamespace(serverInfo=SimpleNamespace(name="example-mcp", version="2.1.0"))
    session_stub = _FakeSession(initialize_result)

    with (
        patch("lfx.base.mcp.util.ClientSession", return_value=session_stub),
        patch("mcp.client.streamable_http.streamablehttp_client", _transport_client()),
    ):
        session, task, transport, _ = await manager._create_streamable_http_session("s1", dict(CONNECTION_PARAMS))
        try:
            assert transport == "streamable_http"
            info = server_info_from_session(session)
            assert info is not None
            assert (info.name, info.version) == ("example-mcp", "2.1.0")
        finally:
            await _shutdown(manager, task)


async def test_server_info_is_none_when_the_server_publishes_none(manager):
    session_stub = _FakeSession(SimpleNamespace(serverInfo=None))

    with (
        patch("lfx.base.mcp.util.ClientSession", return_value=session_stub),
        patch("mcp.client.streamable_http.streamablehttp_client", _transport_client()),
    ):
        session, task, _, _ = await manager._create_streamable_http_session("s2", dict(CONNECTION_PARAMS))
        try:
            assert server_info_from_session(session) is None
        finally:
            await _shutdown(manager, task)


def test_server_info_of_a_session_that_never_handshook_is_none():
    assert server_info_from_session(None) is None
    assert server_info_from_session(SimpleNamespace()) is None


async def test_sse_fallback_is_skipped_when_the_transport_is_pinned(manager):
    """A 404 normally means 'try the legacy transport'; a pinned endpoint does not."""
    response = httpx.Response(404, request=httpx.Request("POST", CONNECTION_PARAMS["url"]))
    failing = MagicMock()
    failing.return_value.__aenter__ = AsyncMock(
        side_effect=httpx.HTTPStatusError("not found", request=response.request, response=response)
    )
    failing.return_value.__aexit__ = AsyncMock(return_value=None)
    sse = _transport_client()

    params = {**CONNECTION_PARAMS, "allow_sse_fallback": False}
    with (
        patch("lfx.base.mcp.util.ClientSession", return_value=_FakeSession(SimpleNamespace(serverInfo=None))),
        patch("mcp.client.streamable_http.streamablehttp_client", failing),
        patch("mcp.client.sse.sse_client", sse),
        pytest.raises(httpx.HTTPStatusError),
    ):
        await manager._create_streamable_http_session("s3", params)
    assert sse.call_count == 0


async def test_sse_fallback_still_runs_for_unpinned_servers(manager):
    response = httpx.Response(404, request=httpx.Request("POST", CONNECTION_PARAMS["url"]))
    failing = MagicMock()
    failing.return_value.__aenter__ = AsyncMock(
        side_effect=httpx.HTTPStatusError("not found", request=response.request, response=response)
    )
    failing.return_value.__aexit__ = AsyncMock(return_value=None)
    sse = MagicMock()
    sse.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
    sse.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("lfx.base.mcp.util.ClientSession", return_value=_FakeSession(SimpleNamespace(serverInfo=None))),
        patch("mcp.client.streamable_http.streamablehttp_client", failing),
        patch("mcp.client.sse.sse_client", sse),
    ):
        _, task, transport, _ = await manager._create_streamable_http_session("s4", dict(CONNECTION_PARAMS))
        try:
            assert transport == "sse"
            assert sse.call_count == 1
        finally:
            await _shutdown(manager, task)


async def test_update_tools_keeps_the_raw_schemas_and_forwards_the_transport_pin():
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    output_schema = {"type": "object", "properties": {"messages": {"type": "array"}}}
    discovered = SimpleNamespace(
        name="search_messages",
        description="Search messages",
        inputSchema=input_schema,
        outputSchema=output_schema,
    )

    client = MCPStreamableHttpClient()
    client.connect_to_server = AsyncMock(return_value=[discovered])
    client._connected = True

    with patch("lfx.base.mcp.util.validate_connector_url_for_ssrf"):
        mode, tools, cache = await update_tools(
            "pinned-server",
            {"url": "https://mcp.example.com/mcp", "mode": "Streamable_HTTP", "allow_sse_fallback": False},
            mcp_streamable_http_client=client,
        )

    assert mode == "Streamable_HTTP"
    assert list(cache) == ["search_messages"]
    assert tools[0].metadata["input_schema"] == input_schema
    assert tools[0].metadata["output_schema"] == output_schema
    assert client.connect_to_server.await_args.kwargs["allow_sse_fallback"] is False


async def test_update_tools_defaults_to_allowing_the_sse_fallback():
    discovered = SimpleNamespace(
        name="search_messages",
        description="",
        inputSchema={"type": "object", "properties": {}},
        outputSchema=None,
    )
    client = MCPStreamableHttpClient()
    client.connect_to_server = AsyncMock(return_value=[discovered])
    client._connected = True

    with patch("lfx.base.mcp.util.validate_connector_url_for_ssrf"):
        await update_tools(
            "vendor-server",
            {"url": "https://mcp.example.com/mcp", "mode": "Streamable_HTTP"},
            mcp_streamable_http_client=client,
        )

    assert client.connect_to_server.await_args.kwargs["allow_sse_fallback"] is True

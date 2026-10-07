"""SSE-mode MCP servers must connect through the legacy SSE transport.

A legacy SSE server (GET opens the event stream, POST ``?session_id=`` carries messages) answers a
Streamable HTTP probe with HTTP 400. That 400 used to be retried as a transient failure, so neither
an explicit ``mode="SSE"`` config nor the Streamable HTTP fallback ever reached the SSE transport.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
import pytest
import uvicorn
from lfx.base.mcp.util import (
    MCPStdioClient,
    MCPStreamableHttpClient,
    _is_transient_streamable_http_error,
    _should_attempt_sse_after_streamable_failure,
    update_tools,
)
from mcp import types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from sse_starlette.sse import AppStatus
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class LegacySseServer:
    """Real pre-Streamable-HTTP MCP server that records rejected Streamable HTTP probes."""

    def __init__(self) -> None:
        self.rejected_probes = 0
        self.url = ""
        self._mcp = Server("legacy-sse")
        self._transport = SseServerTransport("/")

        @self._mcp.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [
                types.Tool(
                    name="echo",
                    description="Echo text back",
                    inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                )
            ]

        @self._mcp.call_tool()
        async def call_tool(_name: str, arguments: dict) -> list[types.TextContent]:
            return [types.TextContent(type="text", text=f"echo:{arguments.get('text')}")]

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return
        request = Request(scope, receive)
        if request.method == "GET":
            async with self._transport.connect_sse(scope, receive, send) as (read, write):
                await self._mcp.run(read, write, self._mcp.create_initialization_options())
            return
        if request.method == "POST":
            if "session_id" not in request.query_params:
                self.rejected_probes += 1
            await self._transport.handle_post_message(scope, receive, send)
            return
        await Response("method not allowed", status_code=405)(scope, receive, send)


@asynccontextmanager
async def _serve(app) -> AsyncIterator[str]:
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="off"))
    serve_task = asyncio.create_task(server.serve())
    while not server.started:
        if serve_task.done():
            serve_task.result()
        await asyncio.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.should_exit = True
        with suppress(asyncio.CancelledError):
            await asyncio.wait_for(serve_task, timeout=5)
        # sse_starlette records uvicorn shutdown in a process-wide flag that closes every later SSE stream.
        AppStatus.should_exit = False


async def _reject_every_request_with_400(scope, receive, send) -> None:
    if scope["type"] == "http":
        await JSONResponse({"error": "missing X-Tenant header"}, status_code=400)(scope, receive, send)


async def _reject_every_request_with_401(scope, receive, send) -> None:
    if scope["type"] == "http":
        await JSONResponse({"error": "invalid token"}, status_code=401)(scope, receive, send)


@pytest.fixture
async def legacy_sse_server() -> AsyncIterator[LegacySseServer]:
    app = LegacySseServer()
    async with _serve(app) as url:
        app.url = url
        yield app


async def _update_tools(url: str, mode: str, client: MCPStreamableHttpClient):
    return await update_tools(
        server_name="legacy-sse",
        server_config={"url": url, "mode": mode},
        mcp_stdio_client=MCPStdioClient(),
        mcp_streamable_http_client=client,
    )


def _status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://legacy-sse.example/")
    return httpx.HTTPStatusError("rejected", request=request, response=httpx.Response(status_code, request=request))


@pytest.mark.asyncio
async def test_should_list_tools_over_sse_without_streamable_probe_when_mode_is_sse(legacy_sse_server):
    client = MCPStreamableHttpClient()
    try:
        mode, tools, _ = await _update_tools(legacy_sse_server.url, "SSE", client)

        assert mode == "SSE"
        assert [tool.name for tool in tools] == ["echo"]
        assert legacy_sse_server.rejected_probes == 0
    finally:
        await client.disconnect()


@pytest.mark.asyncio
async def test_should_run_tool_over_sse_when_mode_is_sse(legacy_sse_server):
    client = MCPStreamableHttpClient()
    try:
        await _update_tools(legacy_sse_server.url, "SSE", client)

        result = await client.run_tool("echo", {"text": "hello"})

        assert [block.text for block in result.content] == ["echo:hello"]
        assert legacy_sse_server.rejected_probes == 0
    finally:
        await client.disconnect()


@pytest.mark.asyncio
async def test_should_fall_back_to_sse_when_streamable_probe_gets_400(legacy_sse_server):
    client = MCPStreamableHttpClient()
    try:
        mode, tools, _ = await _update_tools(legacy_sse_server.url, "Streamable_HTTP", client)

        assert mode == "Streamable_HTTP"
        assert [tool.name for tool in tools] == ["echo"]
        assert legacy_sse_server.rejected_probes == 1
    finally:
        await client.disconnect()


@pytest.mark.asyncio
async def test_should_keep_http_status_in_error_when_both_transports_get_400():
    client = MCPStreamableHttpClient()
    try:
        async with _serve(_reject_every_request_with_400) as url:
            with pytest.raises(ConnectionError) as exc_info:
                await _update_tools(url, "Streamable_HTTP", client)

        assert "HTTP 400" in str(exc_info.value)
    finally:
        await client.disconnect()


@pytest.mark.asyncio
async def test_should_report_rejected_credential_when_sse_mode_gets_401():
    client = MCPStreamableHttpClient()
    try:
        async with _serve(_reject_every_request_with_401) as url:
            with pytest.raises(ConnectionError) as exc_info:
                await _update_tools(url, "SSE", client)

        assert "HTTP 401" in str(exc_info.value)
        assert "credential was refused" in str(exc_info.value)
    finally:
        await client.disconnect()


def test_should_classify_400_as_transport_mismatch_not_transient():
    error = _status_error(400)

    assert _is_transient_streamable_http_error(error) is False
    assert _should_attempt_sse_after_streamable_failure(error) is True


@pytest.mark.parametrize("status_code", [401, 403, 429, 500, 503])
def test_should_not_fall_back_to_sse_for_auth_rate_limit_or_server_errors(status_code):
    assert _should_attempt_sse_after_streamable_failure(_status_error(status_code)) is False

"""Streamable-HTTP transport for the ``langflow-mcp`` (lfx) FastMCP server.

Exposes the single Langflow MCP toolkit — flow authoring, execution, and
``run_assistant`` — at ``/api/v1/agentic/mcp`` so external MCP clients can
reach the running Langflow server without spawning a local stdio process.

The mounted server is ``lfx.mcp.server``: the same tool definitions the local
``lfx-mcp`` stdio bridge ships, so there is exactly one MCP toolkit. Every tool
call goes through the REST API in loopback with the caller's own credentials
(taken from the request headers), so authorization is enforced by the API on
every operation and no tool ever touches the database directly. The ``login``
tool is excluded over HTTP: the caller is already authenticated, and accepting
credentials/server URLs from tool arguments would be a credential-forwarding
surface. The whole endpoint is gated on the ``agentic_experience`` setting
(404 when disabled).
"""

from contextvars import ContextVar
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from lfx.log.logger import logger
from lfx.mcp.client import LangflowClient
from lfx.mcp.server import client_scope
from lfx.mcp.server import mcp as lfx_mcp
from mcp import types
from mcp.server import Server

from langflow.api.utils import CurrentActiveMCPUser
from langflow.api.v1.mcp import ResponseNoOp, StreamableHTTP
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/agentic/mcp", tags=["agentic-mcp"], include_in_schema=False)

# login() would accept credentials and an arbitrary server_url from tool
# arguments; the route already authenticates the caller, so keep it stdio-only.
_HTTP_EXCLUDED_TOOLS = frozenset({"login"})

current_loopback_client_ctx: ContextVar[LangflowClient | None] = ContextVar("current_loopback_client_ctx", default=None)

server: Server = Server("langflow-mcp")


def enforce_agentic_experience() -> None:
    if not get_settings_service().settings.agentic_experience:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This endpoint is not available")


def _loopback_client(request: Request) -> LangflowClient:
    """Build a REST client for this server bound to the caller's own credentials.

    The raw auth headers are forwarded verbatim, so the loopback calls carry
    exactly the identity the route authenticated — no key minting, no
    impersonation surface.
    """
    authorization = request.headers.get("Authorization", "")
    access_token = authorization.removeprefix("Bearer ").strip() or None
    return LangflowClient(
        server_url=str(request.base_url).rstrip("/"),
        api_key=request.headers.get("x-api-key"),
        access_token=access_token,
    )


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return []


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return []


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [tool for tool in await lfx_mcp.list_tools() if tool.name not in _HTTP_EXCLUDED_TOOLS]


@server.call_tool(validate_input=False)
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Delegate to the lfx FastMCP server with the caller's loopback client bound.

    ``validate_input=False`` mirrors FastMCP's own transport registration;
    FastMCP still validates the final arguments via pydantic. The shared
    lowlevel ``request_ctx`` contextvar makes FastMCP's Context (progress/log
    notifications) work through this delegation unchanged.
    """
    if name in _HTTP_EXCLUDED_TOOLS:
        msg = f"Tool '{name}' is not available over HTTP"
        raise ValueError(msg)
    client = current_loopback_client_ctx.get()
    if client is None:
        msg = "Authenticated client is unavailable for this MCP request"
        raise ValueError(msg)
    with client_scope(client):
        return await lfx_mcp.call_tool(name, arguments)


_streamable_http = StreamableHTTP(server)


async def stop_agentic_streamable_http_manager() -> None:
    await _streamable_http.stop()


streamable_http_route_config = {
    "methods": ["GET", "POST", "DELETE"],
    "response_class": ResponseNoOp,
}


@router.head("", dependencies=[Depends(enforce_agentic_experience)])
async def agentic_mcp_health() -> Response:
    return Response()


@router.api_route("", dependencies=[Depends(enforce_agentic_experience)], **streamable_http_route_config)
@router.api_route("/", dependencies=[Depends(enforce_agentic_experience)], **streamable_http_route_config)
async def handle_agentic_streamable_http(request: Request, current_user: CurrentActiveMCPUser) -> Response:
    # current_user enforces authentication; the loopback client then carries the
    # caller's own headers so every tool call re-authenticates at the REST API.
    del current_user
    # Started lazily so the session manager only runs when the endpoint is used
    # (start() is idempotent and cheap once running).
    await _streamable_http.start()
    context_token = current_loopback_client_ctx.set(_loopback_client(request))
    try:
        manager = _streamable_http.get_manager()
        await manager.handle_request(request.scope, request.receive, request._send)  # noqa: SLF001
    except HTTPException:
        raise
    except Exception as exc:
        await logger.aexception(f"Error handling agentic MCP Streamable HTTP request: {exc!s}")
        raise HTTPException(status_code=500, detail="Internal server error in agentic MCP transport") from exc
    finally:
        current_loopback_client_ctx.reset(context_token)
    return ResponseNoOp()

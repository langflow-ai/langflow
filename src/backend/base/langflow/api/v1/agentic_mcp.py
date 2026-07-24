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
surface.

The mount itself is NOT gated on ``agentic_experience``. Every tool here is a
REST call the API already authorizes, and the ``lfx-mcp`` stdio bridge serves
the same toolkit ungated -- gating the whole mount would hold 32 ungated tools
hostage to the one tool that needs the gate, and make HTTP arbitrarily weaker
than stdio for no security gain. Instead ``run_assistant`` alone is excluded
while the gate is off, since it is the only tool that reaches the assistant's
code-generating endpoints.
"""

from contextvars import ContextVar
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from lfx.log.logger import logger
from lfx.mcp.client import LangflowClient
from lfx.mcp.server import client_scope
from lfx.mcp.server import mcp as lfx_mcp
from mcp import types
from mcp.server import Server

from langflow.api.utils import CurrentActiveMCPUser, DbSession
from langflow.api.v1.mcp import ResponseNoOp, StreamableHTTP
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/agentic/mcp", tags=["agentic-mcp"], include_in_schema=False)

# login() would accept credentials and an arbitrary server_url from tool
# arguments; the route already authenticates the caller, so keep it stdio-only.
_HTTP_EXCLUDED_TOOLS = frozenset({"login"})

# run_assistant drives the assistant's codegen endpoints, which agentic_experience gates.
_AGENTIC_GATED_TOOLS = frozenset({"run_assistant"})


def _excluded_tools() -> frozenset[str]:
    """Tools hidden from this transport for the current request."""
    if get_settings_service().settings.agentic_experience:
        return _HTTP_EXCLUDED_TOOLS
    return _HTTP_EXCLUDED_TOOLS | _AGENTIC_GATED_TOOLS


current_loopback_client_ctx: ContextVar[LangflowClient | None] = ContextVar("current_loopback_client_ctx", default=None)

server: Server = Server("langflow-mcp")


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
    excluded = _excluded_tools()
    return [tool for tool in await lfx_mcp.list_tools() if tool.name not in excluded]


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
    if name in _excluded_tools():
        msg = (
            f"Tool '{name}' requires the Langflow Assistant, which is disabled on this server "
            "(LANGFLOW_AGENTIC_EXPERIENCE is not enabled). The other tools remain available."
        )
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


@router.head("")
async def agentic_mcp_health() -> Response:
    return Response()


@router.api_route("", **streamable_http_route_config)
@router.api_route("/", **streamable_http_route_config)
async def handle_agentic_streamable_http(
    request: Request, current_user: CurrentActiveMCPUser, db: DbSession
) -> Response:
    """Dispatch one MCP request, with the caller's loopback client bound.

    ``current_user`` only enforces authentication -- the loopback client carries the caller's
    own headers, so every tool call re-authenticates at the REST API.

    ``db`` is the very session the auth dependency opened (same cached dependency), and FastAPI
    would hold it open for the whole request, tool call included. Every tool then issues a
    loopback REST call that needs its own connection, and on SQLite it waits on the one this
    request is still holding until ``busy_timeout`` (30s) kills it -- so the mount deadlocks on
    the default database. Authentication is finished by now and nothing below reads the session,
    so release it before dispatching.
    """
    del current_user
    await db.close()
    # start() is idempotent; called here so the session manager only runs once the endpoint is used.
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

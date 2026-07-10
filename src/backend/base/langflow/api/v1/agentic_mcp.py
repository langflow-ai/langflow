"""Streamable-HTTP transport for the ``langflow-agentic`` FastMCP server.

Exposes the agentic tools (templates, components, flow inspection, and
``run_assistant``) at ``/api/v1/agentic/mcp`` so external MCP clients can
reach the running Langflow server without spawning a local stdio process.

Every request is authenticated with the same dependency the other MCP HTTP
endpoints use (API key or bearer token), and any tool argument named
``user_id`` is overridden with the authenticated user so a caller can never
act on another user's behalf. The whole surface is gated on the
``agentic_experience`` setting (404 when disabled).
"""

import copy
from contextvars import ContextVar
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from lfx.log.logger import logger
from mcp import types
from mcp.server import Server

from langflow.agentic.mcp.server import mcp as agentic_mcp
from langflow.api.utils import CurrentActiveMCPUser
from langflow.api.v1.mcp import ResponseNoOp, StreamableHTTP
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/agentic/mcp", tags=["agentic-mcp"], include_in_schema=False)

current_agentic_mcp_user_ctx: ContextVar[User | None] = ContextVar("current_agentic_mcp_user_ctx", default=None)

server: Server = Server("langflow-agentic")

_user_scoped_tool_names: set[str] | None = None


def enforce_agentic_experience() -> None:
    if not get_settings_service().settings.agentic_experience:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This endpoint is not available")


async def _tools_accepting_user_id() -> set[str]:
    global _user_scoped_tool_names  # noqa: PLW0603
    if _user_scoped_tool_names is None:
        tools = await agentic_mcp.list_tools()
        _user_scoped_tool_names = {
            tool.name for tool in tools if "user_id" in (tool.inputSchema or {}).get("properties", {})
        }
    return _user_scoped_tool_names


def _without_user_id(tool: types.Tool) -> types.Tool:
    """Hide ``user_id`` from the advertised schema — HTTP resolves it from the authenticated caller."""
    schema: dict[str, Any] = copy.deepcopy(tool.inputSchema or {})
    properties = schema.get("properties", {})
    if "user_id" not in properties:
        return tool
    properties.pop("user_id")
    if "required" in schema:
        schema["required"] = [name for name in schema["required"] if name != "user_id"]
    return tool.model_copy(update={"inputSchema": schema})


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return []


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return []


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [_without_user_id(tool) for tool in await agentic_mcp.list_tools()]


@server.call_tool(validate_input=False)
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Delegate to the FastMCP agentic server with the authenticated user injected.

    ``validate_input=False`` mirrors FastMCP's own transport registration: the
    advertised schema omits ``user_id`` while the underlying tool requires it,
    and FastMCP still validates the final arguments via pydantic. The shared
    lowlevel ``request_ctx`` contextvar makes FastMCP's Context (progress/log
    notifications) work through this delegation unchanged.
    """
    user = current_agentic_mcp_user_ctx.get()
    if user is None:
        msg = "Authenticated user is unavailable for this MCP request"
        raise ValueError(msg)
    if name in await _tools_accepting_user_id():
        arguments = {**arguments, "user_id": str(user.id)}
    return await agentic_mcp.call_tool(name, arguments)


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
    # Started lazily so the session manager only runs when the endpoint is used
    # (start() is idempotent and cheap once running).
    await _streamable_http.start()
    context_token = current_agentic_mcp_user_ctx.set(current_user)
    try:
        manager = _streamable_http.get_manager()
        await manager.handle_request(request.scope, request.receive, request._send)  # noqa: SLF001
    except HTTPException:
        raise
    except Exception as exc:
        await logger.aexception(f"Error handling agentic MCP Streamable HTTP request: {exc!s}")
        raise HTTPException(status_code=500, detail="Internal server error in agentic MCP transport") from exc
    finally:
        current_agentic_mcp_user_ctx.reset(context_token)
    return ResponseNoOp()

import asyncio
from contextlib import AsyncExitStack
from types import MethodType
from typing import Any

import pydantic
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from lfx.log.logger import logger
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from langflow.api.utils import CurrentActiveMCPUser
from langflow.api.v1.mcp_utils import (
    current_user_ctx,
    handle_call_tool,
    handle_list_resources,
    handle_list_tools,
    handle_mcp_errors,
    handle_read_resource,
)
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/mcp", tags=["mcp"])

server = Server("langflow-mcp-server")

DEFAULT_NOTIFICATION_OPTIONS = NotificationOptions(
    prompts_changed=True,
    resources_changed=True,
    tools_changed=True,
)


def _create_initialization_options_with_defaults(
    self,
    notification_options: NotificationOptions | None = None,
    experimental_capabilities: dict[str, dict[str, Any]] | None = None,
):
    """Inject default notification options aligned with Langflow's expectations."""
    options = notification_options or DEFAULT_NOTIFICATION_OPTIONS
    return Server.create_initialization_options(
        self,
        notification_options=options,
        experimental_capabilities=experimental_capabilities,
    )


server.create_initialization_options = MethodType(_create_initialization_options_with_defaults, server)


# Define constants
MAX_RETRIES = 2


def get_enable_progress_notifications() -> bool:
    return get_settings_service().settings.mcp_server_enable_progress_notifications


@server.list_prompts()
async def handle_list_prompts():
    return []


@server.list_resources()
async def handle_global_resources():
    """Handle listing resources for global MCP server."""
    return await handle_list_resources()


@server.read_resource()
async def handle_global_read_resource(uri: str) -> bytes:
    """Handle resource read requests for global MCP server."""
    return await handle_read_resource(uri)


@server.list_tools()
async def handle_global_tools():
    """Handle listing tools for global MCP server."""
    return await handle_list_tools()


@server.call_tool()
@handle_mcp_errors
async def handle_global_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool execution requests for global MCP server."""
    return await handle_call_tool(name, arguments, server)


# Legacy SSE transport (kept for backward compatibility)
sse = SseServerTransport("/api/v1/mcp/")

# Streamable HTTP session manager
_streamable_http_manager: StreamableHTTPSessionManager | None = None
_streamable_http_manager_lock = asyncio.Lock()
_streamable_http_manager_started = False
_streamable_http_manager_stack: AsyncExitStack | None = None


async def _ensure_streamable_http_manager_running() -> None:
    """Start the Streamable HTTP session manager if it isn't already running."""
    global _streamable_http_manager_started, _streamable_http_manager_stack, _streamable_http_manager

    if _streamable_http_manager_started:
        return

    async with _streamable_http_manager_lock:
        if _streamable_http_manager_started:
            return

        # Create a new instance each time we start
        _streamable_http_manager = StreamableHTTPSessionManager(server)
        _streamable_http_manager_stack = AsyncExitStack()
        await _streamable_http_manager_stack.enter_async_context(_streamable_http_manager.run())
        _streamable_http_manager_started = True
        await logger.adebug("Streamable HTTP session manager started for global MCP server")


@router.on_event("startup")
async def _start_streamable_http_manager() -> None:
    await _ensure_streamable_http_manager_running()


@router.on_event("shutdown")
async def _stop_streamable_http_manager() -> None:
    global _streamable_http_manager_started, _streamable_http_manager_stack, _streamable_http_manager

    async with _streamable_http_manager_lock:
        if not _streamable_http_manager_started or _streamable_http_manager_stack is None:
            return

        await _streamable_http_manager_stack.aclose()
        _streamable_http_manager_stack = None
        _streamable_http_manager = None  # Clear the instance so it can be recreated
        _streamable_http_manager_started = False
        await logger.adebug("Streamable HTTP session manager stopped for global MCP server")


def find_validation_error(exc):
    """Searches for a pydantic.ValidationError in the exception chain."""
    while exc:
        if isinstance(exc, pydantic.ValidationError):
            return exc
        exc = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    return None


async def _dispatch_streamable_http(
    request: Request,
    current_user: CurrentActiveMCPUser,
) -> Response:
    """Common handler for Streamable HTTP requests with user context propagation."""
    await _ensure_streamable_http_manager_running()

    await logger.adebug(
        "Handling %s %s via Streamable HTTP for user %s",
        request.method,
        request.url.path,
        current_user.id,
    )

    context_token = current_user_ctx.set(current_user)
    try:
        # Ensure manager is initialized (should be after _ensure_streamable_http_manager_running)
        if _streamable_http_manager is None:
            raise HTTPException(status_code=500, detail="Streamable HTTP manager not initialized")
        await _streamable_http_manager.handle_request(request.scope, request.receive, request._send)  # noqa: SLF001
    except HTTPException:
        raise
    except Exception as exc:
        await logger.aexception(f"Error handling Streamable HTTP request: {exc!s}")
        raise HTTPException(status_code=500, detail="Internal server error in Streamable HTTP transport") from exc
    finally:
        current_user_ctx.reset(context_token)

    # Starlette requires a Response object even after the stream has completed.
    return Response()


@router.api_route("/", methods=["GET", "POST", "DELETE"])
async def handle_streamable_http(request: Request, current_user: CurrentActiveMCPUser):
    """Primary MCP endpoint implementing the Streamable HTTP transport."""
    return await _dispatch_streamable_http(request, current_user)


# Legacy SSE endpoints (kept for backward compatibility)
@router.head("/sse", response_class=HTMLResponse, include_in_schema=False)
async def im_alive():
    return Response()


@router.get("/sse", response_class=StreamingResponse)
async def handle_sse(request: Request, current_user: CurrentActiveMCPUser):
    """Legacy SSE endpoint - redirects to Streamable HTTP for compatibility."""
    # For backward compatibility, redirect SSE requests to Streamable HTTP
    return await _dispatch_streamable_http(request, current_user)

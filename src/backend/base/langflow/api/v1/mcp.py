import asyncio

import pydantic
from anyio import BrokenResourceError
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from lfx.log.logger import logger
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport

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


sse = SseServerTransport("/api/v1/mcp/")


def find_validation_error(exc):
    """Searches for a pydantic.ValidationError in the exception chain."""
    while exc:
        if isinstance(exc, pydantic.ValidationError):
            return exc
        exc = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    return None


@router.head("/sse", response_class=HTMLResponse, include_in_schema=False)
async def im_alive():
    return Response()


@router.get("/sse", response_class=StreamingResponse)
async def handle_sse(request: Request, current_user: CurrentActiveMCPUser):
    msg = f"Starting SSE connection, server name: {server.name}"
    await logger.ainfo(msg)
    token = current_user_ctx.set(current_user)
    try:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:  # noqa: SLF001
            try:
                msg = "Starting SSE connection"
                await logger.adebug(msg)
                msg = f"Stream types: read={type(streams[0])}, write={type(streams[1])}"
                await logger.adebug(msg)

                notification_options = NotificationOptions(
                    prompts_changed=True, resources_changed=True, tools_changed=True
                )
                init_options = server.create_initialization_options(notification_options)
                msg = f"Initialization options: {init_options}"
                await logger.adebug(msg)

                try:
                    await server.run(streams[0], streams[1], init_options)
                except Exception as exc:  # noqa: BLE001
                    validation_error = find_validation_error(exc)
                    if validation_error:
                        msg = "Validation error in MCP:" + str(validation_error)
                        await logger.adebug(msg)
                    else:
                        msg = f"Error in MCP: {exc!s}"
                        await logger.adebug(msg)
                        return
            except BrokenResourceError:
                # Handle gracefully when client disconnects
                await logger.ainfo("Client disconnected from SSE connection")
            except asyncio.CancelledError:
                await logger.ainfo("SSE connection was cancelled")
                raise
            except Exception as e:
                msg = f"Error in MCP: {e!s}"
                await logger.aexception(msg)
                raise
    finally:
        current_user_ctx.reset(token)


@router.post("/")
async def handle_messages(request: Request):
    try:
        await sse.handle_post_message(request.scope, request.receive, request._send)  # noqa: SLF001
    except (BrokenResourceError, BrokenPipeError) as e:
        await logger.ainfo("MCP Server disconnected")
        raise HTTPException(status_code=404, detail=f"MCP Server disconnected, error: {e}") from e
    except Exception as e:
        await logger.aerror(f"Internal server error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") from e

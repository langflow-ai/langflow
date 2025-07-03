import asyncio
import base64
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any, ParamSpec, TypeVar
from urllib.parse import quote, unquote, urlparse
from uuid import uuid4

import pydantic
from anyio import BrokenResourceError
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport
from sqlmodel import select

from langflow.api.utils import CurrentActiveMCPUser
from langflow.api.v1.endpoints import simple_run_flow
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.base.mcp.constants import MAX_MCP_TOOL_NAME_LENGTH
from langflow.base.mcp.util import get_flow_snake_case, sanitize_mcp_name
from langflow.helpers.flow import json_schema_from_flow
from langflow.schema.message import Message
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import (
    get_db_service,
    get_settings_service,
    get_storage_service,
    session_scope,
)
from langflow.services.storage.utils import build_content_type_from_extension

T = TypeVar("T")
P = ParamSpec("P")


def handle_mcp_errors(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """Decorator to handle MCP endpoint errors consistently."""

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            msg = f"Error in {func.__name__}: {e!s}"
            logger.exception(msg)
            raise

    return wrapper


async def with_db_session(operation: Callable[[Any], Awaitable[T]]) -> T:
    """Execute an operation within a database session context."""
    async with session_scope() as session:
        return await operation(session)


class MCPConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.enable_progress_notifications = None
        return cls._instance


def get_mcp_config():
    return MCPConfig()


router = APIRouter(prefix="/mcp", tags=["mcp"])

server = Server("langflow-mcp-server")

# Create a context variable to store the current user
current_user_ctx: ContextVar[User] = ContextVar("current_user_ctx")

# Define constants
MAX_RETRIES = 2


def get_enable_progress_notifications() -> bool:
    return get_settings_service().settings.mcp_server_enable_progress_notifications


@server.list_prompts()
async def handle_list_prompts():
    return []


@server.list_resources()
async def handle_list_resources():
    resources = []
    try:
        db_service = get_db_service()
        storage_service = get_storage_service()
        settings_service = get_settings_service()

        # Build full URL from settings
        host = getattr(settings_service.settings, "host", "localhost")
        port = getattr(settings_service.settings, "port", 3000)

        base_url = f"http://{host}:{port}".rstrip("/")

        async with db_service.with_session() as session:
            flows = (await session.exec(select(Flow))).all()

            for flow in flows:
                if flow.id:
                    try:
                        files = await storage_service.list_files(flow_id=str(flow.id))
                        for file_name in files:
                            # URL encode the filename
                            safe_filename = quote(file_name)
                            resource = types.Resource(
                                uri=f"{base_url}/api/v1/files/{flow.id}/{safe_filename}",
                                name=file_name,
                                description=f"File in flow: {flow.name}",
                                mimeType=build_content_type_from_extension(file_name),
                            )
                            resources.append(resource)
                    except FileNotFoundError as e:
                        msg = f"Error listing files for flow {flow.id}: {e}"
                        logger.debug(msg)
                        continue
    except Exception as e:
        msg = f"Error in listing resources: {e!s}"
        logger.exception(msg)
        raise
    return resources


@server.read_resource()
async def handle_read_resource(uri: str) -> bytes:
    """Handle resource read requests."""
    try:
        # Parse the URI properly
        parsed_uri = urlparse(str(uri))
        # Path will be like /api/v1/files/{flow_id}/{filename}
        path_parts = parsed_uri.path.split("/")
        # Remove empty strings from split
        path_parts = [p for p in path_parts if p]

        # The flow_id and filename should be the last two parts
        two = 2
        if len(path_parts) < two:
            msg = f"Invalid URI format: {uri}"
            raise ValueError(msg)

        flow_id = path_parts[-2]
        filename = unquote(path_parts[-1])  # URL decode the filename

        storage_service = get_storage_service()

        # Read the file content
        content = await storage_service.get_file(flow_id=flow_id, file_name=filename)
        if not content:
            msg = f"File {filename} not found in flow {flow_id}"
            raise ValueError(msg)

        # Ensure content is base64 encoded
        if isinstance(content, str):
            content = content.encode()
        return base64.b64encode(content)
    except Exception as e:
        msg = f"Error reading resource {uri}: {e!s}"
        logger.exception(msg)
        raise


@server.list_tools()
async def handle_list_tools():
    tools = []
    try:
        db_service = get_db_service()
        async with db_service.with_session() as session:
            flows = (await session.exec(select(Flow))).all()

            existing_names = set()
            for flow in flows:
                if flow.user_id is None:
                    continue

                base_name = sanitize_mcp_name(flow.name)
                name = base_name[:MAX_MCP_TOOL_NAME_LENGTH]
                if name in existing_names:
                    i = 1
                    while True:
                        suffix = f"_{i}"
                        truncated_base = base_name[: MAX_MCP_TOOL_NAME_LENGTH - len(suffix)]
                        candidate = f"{truncated_base}{suffix}"
                        if candidate not in existing_names:
                            name = candidate
                            break
                        i += 1
                try:
                    tool = types.Tool(
                        name=name,
                        description=f"{flow.id}: {flow.description}"
                        if flow.description
                        else f"Tool generated from flow: {name}",
                        inputSchema=json_schema_from_flow(flow),
                    )
                    tools.append(tool)
                    existing_names.add(name)
                except Exception as e:  # noqa: BLE001
                    msg = f"Error in listing tools: {e!s} from flow: {base_name}"
                    logger.warning(msg)
                    continue
    except Exception as e:
        msg = f"Error in listing tools: {e!s}"
        logger.exception(msg)
        raise
    return tools


@server.call_tool()
@handle_mcp_errors
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool execution requests."""
    mcp_config = get_mcp_config()
    if mcp_config.enable_progress_notifications is None:
        settings_service = get_settings_service()
        mcp_config.enable_progress_notifications = settings_service.settings.mcp_server_enable_progress_notifications

    current_user = current_user_ctx.get()

    async def execute_tool(session):
        # get flow id from name
        flow = await get_flow_snake_case(name, current_user.id, session)
        if not flow:
            msg = f"Flow with name '{name}' not found"
            raise ValueError(msg)

        # Process inputs
        processed_inputs = dict(arguments)

        # Initial progress notification
        if mcp_config.enable_progress_notifications and (progress_token := server.request_context.meta.progressToken):
            await server.request_context.session.send_progress_notification(
                progress_token=progress_token, progress=0.0, total=1.0
            )

        conversation_id = str(uuid4())
        input_request = SimplifiedAPIRequest(
            input_value=processed_inputs.get("input_value", ""), session_id=conversation_id
        )

        async def send_progress_updates():
            if not (mcp_config.enable_progress_notifications and server.request_context.meta.progressToken):
                return

            try:
                progress = 0.0
                while True:
                    await server.request_context.session.send_progress_notification(
                        progress_token=progress_token, progress=min(0.9, progress), total=1.0
                    )
                    progress += 0.1
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                if mcp_config.enable_progress_notifications:
                    await server.request_context.session.send_progress_notification(
                        progress_token=progress_token, progress=1.0, total=1.0
                    )
                raise

        collected_results = []
        try:
            progress_task = None
            if mcp_config.enable_progress_notifications and server.request_context.meta.progressToken:
                progress_task = asyncio.create_task(send_progress_updates())

            try:
                try:
                    result = await simple_run_flow(
                        flow=flow,
                        input_request=input_request,
                        stream=False,
                        api_key_user=current_user,
                    )
                    # Process all outputs and messages
                    for run_output in result.outputs:
                        for component_output in run_output.outputs:
                            # Handle messages
                            for msg in component_output.messages or []:
                                text_content = types.TextContent(type="text", text=msg.message)
                                collected_results.append(text_content)
                            # Handle results
                            for value in (component_output.results or {}).values():
                                if isinstance(value, Message):
                                    text_content = types.TextContent(type="text", text=value.get_text())
                                    collected_results.append(text_content)
                                else:
                                    collected_results.append(types.TextContent(type="text", text=str(value)))
                except Exception as e:  # noqa: BLE001
                    error_msg = f"Error Executing the {flow.name} tool. Error: {e!s}"
                    collected_results.append(types.TextContent(type="text", text=error_msg))

                return collected_results
            finally:
                if progress_task:
                    progress_task.cancel()
                    await asyncio.wait([progress_task])
                    if not progress_task.cancelled() and (exc := progress_task.exception()) is not None:
                        raise exc

        except Exception:
            if mcp_config.enable_progress_notifications and (
                progress_token := server.request_context.meta.progressToken
            ):
                await server.request_context.session.send_progress_notification(
                    progress_token=progress_token, progress=1.0, total=1.0
                )
            raise

    try:
        return await with_db_session(execute_tool)
    except Exception as e:
        msg = f"Error executing tool {name}: {e!s}"
        logger.exception(msg)
        raise


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
    logger.info(msg)
    token = current_user_ctx.set(current_user)
    try:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            try:
                msg = "Starting SSE connection"
                logger.debug(msg)
                msg = f"Stream types: read={type(streams[0])}, write={type(streams[1])}"
                logger.debug(msg)

                notification_options = NotificationOptions(
                    prompts_changed=True, resources_changed=True, tools_changed=True
                )
                init_options = server.create_initialization_options(notification_options)
                msg = f"Initialization options: {init_options}"
                logger.debug(msg)

                try:
                    await server.run(streams[0], streams[1], init_options)
                except Exception as exc:  # noqa: BLE001
                    validation_error = find_validation_error(exc)
                    if validation_error:
                        msg = "Validation error in MCP:" + str(validation_error)
                        logger.debug(msg)
                    else:
                        msg = f"Error in MCP: {exc!s}"
                        logger.debug(msg)
                        return
            except BrokenResourceError:
                # Handle gracefully when client disconnects
                logger.info("Client disconnected from SSE connection")
            except asyncio.CancelledError:
                logger.info("SSE connection was cancelled")
                raise
            except Exception as e:
                msg = f"Error in MCP: {e!s}"
                logger.exception(msg)
                raise
    finally:
        current_user_ctx.reset(token)


@router.post("/")
async def handle_messages(request: Request):
    try:
        await sse.handle_post_message(request.scope, request.receive, request._send)
    except (BrokenResourceError, BrokenPipeError) as e:
        logger.info("MCP Server disconnected")
        raise HTTPException(status_code=404, detail=f"MCP Server disconnected, error: {e}") from e
    except Exception as e:
        logger.error(f"Internal server error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") from e

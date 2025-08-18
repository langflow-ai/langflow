"""Common MCP handler functions shared between mcp.py and mcp_projects.py.

This module serves as the single source of truth for MCP functionality.
"""

import asyncio
import base64
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any, ParamSpec, TypeVar
from urllib.parse import quote, unquote, urlparse
from uuid import uuid4

from loguru import logger
from mcp import types
from sqlmodel import select

from langflow.api.v1.endpoints import simple_run_flow
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.base.mcp.constants import MAX_MCP_TOOL_NAME_LENGTH
from langflow.base.mcp.util import get_flow_snake_case, get_unique_name, sanitize_mcp_name
from langflow.helpers.flow import json_schema_from_flow
from langflow.schema.message import Message
from langflow.services.database.models import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, get_storage_service, session_scope
from langflow.services.storage.utils import build_content_type_from_extension

T = TypeVar("T")
P = ParamSpec("P")

# Create context variables
current_user_ctx: ContextVar[User] = ContextVar("current_user_ctx")


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


async def handle_list_resources(project_id=None):
    """Handle listing resources for MCP.

    Args:
        project_id: Optional project ID to filter resources by project
    """
    resources = []
    try:
        storage_service = get_storage_service()
        settings_service = get_settings_service()

        # Build full URL from settings
        host = getattr(settings_service.settings, "host", "localhost")
        port = getattr(settings_service.settings, "port", 3000)

        base_url = f"http://{host}:{port}".rstrip("/")

        async with session_scope() as session:
            # Build query based on whether project_id is provided
            flows_query = select(Flow).where(Flow.folder_id == project_id) if project_id else select(Flow)

            flows = (await session.exec(flows_query)).all()

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


async def handle_call_tool(
    name: str, arguments: dict, server, project_id=None, *, is_action=False
) -> list[types.TextContent]:
    """Handle tool execution requests.

    Args:
        name: Tool name
        arguments: Tool arguments
        server: MCP server instance
        project_id: Optional project ID to filter flows by project
        is_action: Whether to use action name for flow lookup
    """
    mcp_config = get_mcp_config()
    if mcp_config.enable_progress_notifications is None:
        settings_service = get_settings_service()
        mcp_config.enable_progress_notifications = settings_service.settings.mcp_server_enable_progress_notifications

    current_user = current_user_ctx.get()

    async def execute_tool(session):
        # Get flow id from name
        flow = await get_flow_snake_case(name, current_user.id, session, is_action=is_action)
        if not flow:
            msg = f"Flow with name '{name}' not found"
            raise ValueError(msg)

        # If project_id is provided, verify the flow belongs to the project
        if project_id and flow.folder_id != project_id:
            msg = f"Flow '{name}' not found in project {project_id}"
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

        async def send_progress_updates(progress_token):
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
                progress_task = asyncio.create_task(send_progress_updates(server.request_context.meta.progressToken))

            try:
                try:
                    result = await simple_run_flow(
                        flow=flow,
                        input_request=input_request,
                        stream=False,
                        api_key_user=current_user,
                    )
                    # Process all outputs and messages, ensuring no duplicates
                    processed_texts = set()

                    def add_result(text: str):
                        if text not in processed_texts:
                            processed_texts.add(text)
                            collected_results.append(types.TextContent(type="text", text=text))

                    for run_output in result.outputs:
                        for component_output in run_output.outputs:
                            # Handle messages
                            for msg in component_output.messages or []:
                                add_result(msg.message)
                            # Handle results
                            for value in (component_output.results or {}).values():
                                if isinstance(value, Message):
                                    add_result(value.get_text())
                                else:
                                    add_result(str(value))
                except Exception as e:  # noqa: BLE001
                    error_msg = f"Error Executing the {flow.name} tool. Error: {e!s}"
                    collected_results.append(types.TextContent(type="text", text=error_msg))

                return collected_results
            finally:
                if progress_task:
                    progress_task.cancel()
                    await asyncio.gather(progress_task, return_exceptions=True)

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


async def handle_list_tools(project_id=None, *, mcp_enabled_only=False):
    """Handle listing tools for MCP.

    Args:
        project_id: Optional project ID to filter tools by project
        mcp_enabled_only: Whether to filter for MCP-enabled flows only
    """
    tools = []
    try:
        async with session_scope() as session:
            # Build query based on parameters
            if project_id:
                # Filter flows by project and optionally by MCP enabled status
                flows_query = select(Flow).where(Flow.folder_id == project_id, Flow.is_component == False)  # noqa: E712
                if mcp_enabled_only:
                    flows_query = flows_query.where(Flow.mcp_enabled == True)  # noqa: E712
            else:
                # Get all flows
                flows_query = select(Flow)

            flows = (await session.exec(flows_query)).all()

            existing_names = set()
            for flow in flows:
                if flow.user_id is None:
                    continue

                # For project-specific tools, use action names if available
                if project_id:
                    base_name = (
                        sanitize_mcp_name(flow.action_name) if flow.action_name else sanitize_mcp_name(flow.name)
                    )
                    name = get_unique_name(base_name, MAX_MCP_TOOL_NAME_LENGTH, existing_names)
                    description = flow.action_description or (
                        flow.description if flow.description else f"Tool generated from flow: {name}"
                    )
                else:
                    # For global tools, use simple sanitized names
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
                    description = (
                        f"{flow.id}: {flow.description}" if flow.description else f"Tool generated from flow: {name}"
                    )

                try:
                    tool = types.Tool(
                        name=name,
                        description=description,
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

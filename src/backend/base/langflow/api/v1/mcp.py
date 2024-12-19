import asyncio
import base64
from urllib.parse import quote, urlparse, unquote
import json
import logging
import traceback
from contextvars import ContextVar
from typing import Annotated
from uuid import UUID, uuid4

import pydantic
from anyio import BrokenResourceError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport
from sqlmodel import select
from starlette.background import BackgroundTasks

from langflow.api.v1.chat import build_flow
from langflow.api.v1.schemas import InputValueRequest
from langflow.graph import Graph
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models import Flow, User
from langflow.services.deps import get_db_service, get_session, get_settings_service, get_storage_service
from langflow.services.storage.utils import build_content_type_from_extension

logger = logging.getLogger(__name__)
if False:
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Enable debug logging for MCP package
    mcp_logger = logging.getLogger("mcp")
    mcp_logger.setLevel(logging.DEBUG)
    if not mcp_logger.handlers:
        mcp_logger.addHandler(handler)

    logger.debug("MCP module loaded - debug logging enabled")

enable_progress_notifications = get_settings_service().settings.mcp_server_enable_progress_notifications

router = APIRouter(prefix="/mcp", tags=["mcp"])

server = Server("langflow-mcp-server")

# Create a context variable to store the current user
current_user_ctx: ContextVar[User] = ContextVar("current_user_ctx")


def json_schema_from_flow(flow: Flow) -> dict:
    """Generate JSON schema from flow input nodes."""
    # Get the flow's data which contains the nodes and their configurations
    flow_data = flow.data if flow.data else {}

    graph = Graph.from_payload(flow_data)
    input_nodes = [vertex for vertex in graph.vertices if vertex.is_input]

    properties = {}
    required = []
    for node in input_nodes:
        node_data = node.data["node"]
        template = node_data["template"]

        for field_name, field_data in template.items():
            if field_data != "Component" and field_data.get("show", False) and not field_data.get("advanced", False):
                field_type = field_data.get("type", "string")
                properties[field_name] = {
                    "type": field_type,
                    "description": field_data.get("info", f"Input for {field_name}"),
                }
                # Update field_type in properties after determining the JSON Schema type
                if field_type == "str":
                    field_type = "string"
                elif field_type == "int":
                    field_type = "integer"
                elif field_type == "float":
                    field_type = "number"
                elif field_type == "bool":
                    field_type = "boolean"
                else:
                    logger.warning(f"Unknown field type: {field_type} defaulting to string")
                    field_type = "string"
                properties[field_name]["type"] = field_type

                if field_data.get("required", False):
                    required.append(field_name)

    return {"type": "object", "properties": properties, "required": required}


@server.list_prompts()
async def handle_list_prompts():
    return []


@server.list_resources()
async def handle_list_resources():
    try:
        session = await anext(get_session())
        storage_service = get_storage_service()
        settings_service = get_settings_service()

        # Build full URL from settings
        host = getattr(settings_service.settings, "holst", "localhost")
        port = getattr(settings_service.settings, "port", 3000)

        base_url = f"http://{host}:{port}".rstrip("/")

        flows = (await session.exec(select(Flow))).all()
        resources = []

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
                except Exception as e:
                    logger.debug(f"Error listing files for flow {flow.id}: {e}")
                    continue

        return resources
    except Exception as e:
        logger.error(f"Error in listing resources: {e!s}")
        trace = traceback.format_exc()
        logger.error(trace)
        raise


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
        if len(path_parts) < 2:
            raise ValueError(f"Invalid URI format: {uri}")

        flow_id = path_parts[-2]
        filename = unquote(path_parts[-1])  # URL decode the filename

        storage_service = get_storage_service()

        # Read the file content
        content = await storage_service.get_file(flow_id=flow_id, file_name=filename)
        if not content:
            raise ValueError(f"File {filename} not found in flow {flow_id}")

        # Ensure content is base64 encoded
        if isinstance(content, str):
            content = content.encode()
        return base64.b64encode(content)
    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e!s}")
        trace = traceback.format_exc()
        logger.error(trace)
        raise


@server.list_tools()
async def handle_list_tools():
    try:
        session = await anext(get_session())
        flows = (await session.exec(select(Flow))).all()
        tools = []

        for flow in flows:
            if flow.user_id is None:
                continue

            tool = types.Tool(
                name=str(flow.id),  # Use flow.id instead of name
                description=f"{flow.name}: {flow.description}"
                if flow.description
                else f"Tool generated from flow: {flow.name}",
                inputSchema=json_schema_from_flow(flow),
            )
            tools.append(tool)

        return tools
    except Exception as e:
        logger.error(f"Error in listing tools: {e!s}")
        trace = traceback.format_exc()
        logger.error(trace)
        raise e


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool execution requests."""
    try:
        session = await anext(get_session())
        background_tasks = BackgroundTasks()

        try:
            current_user = current_user_ctx.get()
        except LookupError:
            raise ValueError("No authenticated user found in context")

        flow = (await session.exec(select(Flow).where(Flow.id == UUID(name)))).first()

        if not flow:
            raise ValueError(f"Flow with id '{name}' not found")

        # Process inputs
        processed_inputs = {}
        for key, value in arguments.items():
            processed_inputs[key] = value

        # Initial progress notification
        if enable_progress_notifications and (progress_token := server.request_context.meta.progressToken):
            await server.request_context.session.send_progress_notification(
                progress_token=progress_token, progress=0.0, total=1.0
            )

        conversation_id = str(uuid4())
        input_request = InputValueRequest(
            input_value=processed_inputs.get("input_value", ""), components=[], type="chat", session=conversation_id
        )

        async def send_progress_updates():
            if not (enable_progress_notifications and server.request_context.meta.progressToken):
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
                # Send final 100% progress
                if enable_progress_notifications:
                    await server.request_context.session.send_progress_notification(
                        progress_token=progress_token, progress=1.0, total=1.0
                    )
                raise

        db_service = get_db_service()
        collected_results = []
        async with db_service.with_async_session() as async_session:
            try:
                progress_task = asyncio.create_task(send_progress_updates())

                try:
                    response = await build_flow(
                        flow_id=UUID(name),
                        inputs=input_request,
                        background_tasks=background_tasks,
                        current_user=current_user,
                        session=async_session,
                    )

                    async for line in response.body_iterator:
                        if not line:
                            continue
                        try:
                            event_data = json.loads(line)
                            if event_data.get("event") == "end_vertex":
                                message = (
                                    event_data.get("data", {})
                                    .get("build_data", {})
                                    .get("data", {})
                                    .get("results", {})
                                    .get("message", {})
                                    .get("text", "")
                                )
                                if message:
                                    collected_results.append(types.TextContent(type="text", text=str(message)))
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse event data: {line}")
                            continue

                    return collected_results
                finally:
                    progress_task.cancel()
                    try:
                        await progress_task
                    except asyncio.CancelledError:
                        pass
            except Exception as e:
                logger.error(f"Error in async session: {e}")
                raise

    except Exception as e:
        context = server.request_context
        # Send error progress if there's an exception
        if enable_progress_notifications and (progress_token := context.meta.progressToken):
            await server.request_context.session.send_progress_notification(
                progress_token=progress_token, progress=1.0, total=1.0
            )
        logger.error(f"Error executing tool {name}: {e!s}")
        trace = traceback.format_exc()
        logger.error(trace)
        raise


sse = SseServerTransport("/api/v1/mcp/")


@router.get("/sse", response_class=StreamingResponse)
async def handle_sse(request: Request, current_user: Annotated[User, Depends(get_current_active_user)]):
    token = current_user_ctx.set(current_user)
    try:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            try:
                logger.debug("Starting SSE connection")
                logger.debug(f"Stream types: read={type(streams[0])}, write={type(streams[1])}")

                notification_options = NotificationOptions(
                    prompts_changed=True, resources_changed=True, tools_changed=True
                )
                init_options = server.create_initialization_options(notification_options)
                logger.debug(f"Initialization options: {init_options}")

                try:
                    await server.run(streams[0], streams[1], init_options)
                except (pydantic.ValidationError, ExceptionGroup) as exc:
                    validation_error = None

                    # For ExceptionGroup, find the validation error if present
                    if isinstance(exc, ExceptionGroup):
                        for inner_exc in exc.exceptions:
                            if isinstance(inner_exc, pydantic.ValidationError):
                                validation_error = inner_exc
                                break
                    elif isinstance(exc, pydantic.ValidationError):
                        validation_error = exc

                    # Handle the validation error if found
                    if validation_error and any("cancelled" in err["input"] for err in validation_error.errors()):
                        logger.debug("Ignoring validation error for cancelled notification")
                    else:
                        # For other errors, log as error but don't crash
                        logger.error(f"Validation error in MCP: {exc}")
                        logger.debug(f"Failed message type: {type(exc).__name__}")
                        if validation_error:
                            logger.debug(f"Validation error details: {validation_error.errors()}")
                    return
            except BrokenResourceError:
                # Handle gracefully when client disconnects
                logger.info("Client disconnected from SSE connection")
            except asyncio.CancelledError:
                logger.info("SSE connection was cancelled")
            except Exception as e:
                logger.error(f"Error in MCP: {e!s}")
                trace = traceback.format_exc()
                logger.error(trace)
                raise
    finally:
        current_user_ctx.reset(token)


@router.post("/")
async def handle_messages(request: Request, current_user: Annotated[User, Depends(get_current_active_user)]):
    await sse.handle_post_message(request.scope, request.receive, request._send)

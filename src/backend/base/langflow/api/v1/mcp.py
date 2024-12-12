import asyncio
import json
import logging
import traceback
from contextvars import ContextVar
from typing import Annotated
from uuid import UUID, uuid4

from anyio import BrokenResourceError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from mcp import types
from mcp.server import Server, NotificationOptions
from mcp.server.sse import SseServerTransport
from pydantic import ValidationError
from sqlmodel import select
from starlette.background import BackgroundTasks

from langflow.api.v1.chat import build_flow
from langflow.api.v1.schemas import InputValueRequest
from langflow.graph import Graph
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models import Flow, User
from langflow.services.deps import get_db_service, get_session

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
    return []


@server.list_tools()
async def handle_list_tools():
    try:
        session = await anext(get_session())
        flows = (await session.exec(select(Flow))).all()
        tools = []
        name_count = {}  # Track name occurrences

        for flow in flows:
            if flow.user_id is None:
                continue
            # Generate unique name by appending _N if needed
            base_name = flow.name
            if base_name in name_count:
                name_count[base_name] += 1
                unique_name = f"{base_name}_{name_count[base_name]}"
            else:
                name_count[base_name] = 0
                unique_name = base_name

            tool = types.Tool(
                name=str(flow.id),  # Use flow.id instead of name
                description=f"{unique_name}: {flow.description}"
                if flow.description
                else f"Tool generated from flow: {unique_name}",
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

        # Send initial progress notification
        # if progress_token := context.meta.progressToken:
        #    await context.session.send_progress_notification(
        #        progress_token=progress_token,
        #        progress=0.5,
        #        total=1.0
        #    )

        conversation_id = str(uuid4())
        input_request = InputValueRequest(
            input_value=processed_inputs["input_value"], components=[], type="chat", session=conversation_id
        )

        result = ""
        db_service = get_db_service()
        async with db_service.with_async_session() as async_session:
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
                            result += (
                                event_data.get("data", {})
                                .get("build_data", {})
                                .get("data", {})
                                .get("results", {})
                                .get("message", {})
                                .get("text", "")
                            )
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse event data: {line}")
                        continue
            except asyncio.CancelledError as e:
                logger.info(f"Request was cancelled: {e!s}")
                # Create a proper cancellation notification
                # notification = types.ProgressNotification(
                #    method="notifications/progress",
                #    params=types.ProgressNotificationParams(
                #        progressToken=str(uuid4()),
                #        progress=1.0
                #    ),
                # )
                # await server.request_context.session.send_notification(notification)
                return [types.TextContent(type="text", text=f"Request cancelled: {e!s}")]

        # Send final progress notification
        # if progress_token:
        #    await context.session.send_progress_notification(
        #        progress_token=progress_token,
        #        progress=1.0,
        #        total=1.0
        #    )
        print(result)

        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e!s}")
        trace = traceback.format_exc()
        logger.error(trace)
        raise


sse = SseServerTransport("/api/v1/mcp")


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

                await server.run(streams[0], streams[1], init_options)
            except ValidationError as e:
                logger.warning(f"Validation error in MCP: {e}")
                logger.debug(f"Failed message type: {type(e).__name__}")
                logger.debug(f"Validation error details: {e.errors()}")
                # Add more details about the failed validation
                if hasattr(e, "model"):
                    logger.debug(f"Failed validation model: {e.model.__name__}")
                if hasattr(e, "raw_errors"):
                    logger.debug(f"Raw validation errors: {e.raw_errors}")
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

# import asyncio
# import base64
# import json
# import logging
# from contextvars import ContextVar
# from datetime import datetime, timezone
# from typing import Annotated
# from urllib.parse import quote, unquote, urlparse
# from uuid import UUID, uuid4

# from anyio import BrokenResourceError
# from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
# from fastapi.responses import StreamingResponse
# from langflow.api.v1.chat import build_flow_and_stream
# from langflow.base.mcp.util import get_flow_snake_case
# from langflow.services.storage.utils import build_content_type_from_extension
# from mcp import types
# from mcp.server import NotificationOptions, Server
# from mcp.server.sse import SseServerTransport
# from sqlalchemy.orm import selectinload
# from sqlmodel import select

# from langflow.api.v1.mcp import (
#     current_user_ctx,
#     get_mcp_config,
#     handle_mcp_errors,
#     server,
#     with_db_session,
# )
# from langflow.api.v1.schemas import InputValueRequest, MCPSettings
# from langflow.helpers.flow import json_schema_from_flow
# from langflow.services.auth.utils import get_current_active_user
# from langflow.services.database.models import Flow, Folder, User
# from langflow.services.deps import get_db_service, get_settings_service, get_storage_service

# logger = logging.getLogger(__name__)
# router = APIRouter(prefix="/mcp/project", tags=["mcp_projects"])

# # Create a context variable to store the current project
# current_project_ctx: ContextVar[UUID | None] = ContextVar("current_project_ctx", default=None)

# # Create a mapping of project-specific SSE transports
# project_sse_transports = {}


# def get_project_sse(project_id: UUID) -> SseServerTransport:
#     """Get or create an SSE transport for a specific project."""
#     project_id_str = str(project_id)
#     if project_id_str not in project_sse_transports:
#         project_sse_transports[project_id_str] = SseServerTransport(f"/api/v1/mcp/project/{project_id_str}/")
#     return project_sse_transports[project_id_str]


# @router.get("/{project_id}", response_model=list[MCPSettings])
# async def list_project_tools(
#     project_id: UUID,
#     current_user: Annotated[User, Depends(get_current_active_user)],
#     *,
#     mcp_enabled_only: bool = True,
# ):
#     """List all tools in a project that are enabled for MCP."""
#     tools: list[MCPSettings] = []
#     try:
#         db_service = get_db_service()
#         async with db_service.with_session() as session:
#             # Fetch the project first to verify it exists and belongs to the current user
#             project = (
#                 await session.exec(
#                     select(Folder)
#                     .options(selectinload(Folder.flows))
#                     .where(Folder.id == project_id, Folder.user_id == current_user.id)
#                 )
#             ).first()

#             if not project:
#                 raise HTTPException(status_code=404, detail="Project not found")

#             # Query flows in the project
#             flows_query = select(Flow).where(Flow.folder_id == project_id)

#             # Optionally filter for MCP-enabled flows only
#             if mcp_enabled_only:
#                 flows_query = flows_query.where(Flow.mcp_enabled == True)

#             flows = (await session.exec(flows_query)).all()

#             for flow in flows:
#                 if flow.user_id is None:
#                     continue

#                 # Format the flow name according to MCP conventions (snake_case)
#                 flow_name = "_".join(flow.name.lower().split())

#                 # Use action_name and action_description if available, otherwise use defaults
#                 name = flow.action_name or flow_name
#                 description = flow.action_description or (
#                     flow.description if flow.description else f"Tool generated from flow: {flow_name}"
#                 )

#                 tool = {
#                     "id": str(flow.id),
#                     "action_name": name,
#                     "action_description": description,
#                     "mcp_enabled": flow.mcp_enabled,
#                     "inputSchema": json_schema_from_flow(flow),
#                     "name": flow.name,
#                     "description": flow.description,
#                 }
#                 tools.append(tool)

#     except Exception as e:
#         msg = f"Error listing project tools: {e!s}"
#         logger.exception(msg)
#         raise HTTPException(status_code=500, detail=str(e)) from e

#     return tools


# def project_snake_case(project_name: str) -> str:
#     """Convert a project name to a snake case string."""
#     return "_".join(project_name.lower().split())


# # Project-specific MCP server instance for handling project-specific tools
# class ProjectMCPServer:
#     def __init__(self, project_name: str):
#         # change to project name
#         self.project_name = project_snake_case(project_name)

#         self.server = Server(f"langflow-mcp-project-{self.project_name}")
#         logger.warning(f"Project MCP server initialized for project {self.project_name}")
#         logger.warning(f"Project MCP server Name: {self.server.name}")

#         @self.server.list_prompts()
#         async def handle_list_prompts():
#             return []

#         @self.server.list_resources()
#         async def handle_list_resources():
#             resources = []
#             try:
#                 db_service = get_db_service()
#                 storage_service = get_storage_service()
#                 settings_service = get_settings_service()

#                 # Build full URL from settings
#                 host = getattr(settings_service.settings, "host", "localhost")
#                 port = getattr(settings_service.settings, "port", 3000)

#                 base_url = f"http://{host}:{port}".rstrip("/")

#                 async with db_service.with_session() as session:
#                     flows = (await session.exec(select(Flow))).all()

#                     for flow in flows:
#                         if flow.id:
#                             try:
#                                 files = await storage_service.list_files(flow_id=str(flow.id))
#                                 for file_name in files:
#                                     # URL encode the filename
#                                     safe_filename = quote(file_name)
#                                     resource = types.Resource(
#                                         uri=f"{base_url}/api/v1/files/{flow.id}/{safe_filename}",
#                                         name=file_name,
#                                         description=f"File in flow: {flow.name}",
#                                         mimeType=build_content_type_from_extension(file_name),
#                                     )
#                                     resources.append(resource)
#                             except FileNotFoundError as e:
#                                 msg = f"Error listing files for flow {flow.id}: {e}"
#                                 logger.debug(msg)
#                                 continue
#             except Exception as e:
#                 msg = f"Error in listing resources: {e!s}"
#                 logger.exception(msg)
#                 raise
#             return resources

#         @server.read_resource()
#         async def handle_read_resource(uri: str) -> bytes:
#             """Handle resource read requests."""
#             try:
#                 # Parse the URI properly
#                 parsed_uri = urlparse(str(uri))
#                 # Path will be like /api/v1/files/{flow_id}/{filename}
#                 path_parts = parsed_uri.path.split("/")
#                 # Remove empty strings from split
#                 path_parts = [p for p in path_parts if p]

#                 # The flow_id and filename should be the last two parts
#                 two = 2
#                 if len(path_parts) < two:
#                     msg = f"Invalid URI format: {uri}"
#                     raise ValueError(msg)

#                 flow_id = path_parts[-2]
#                 filename = unquote(path_parts[-1])  # URL decode the filename

#                 storage_service = get_storage_service()

#                 # Read the file content
#                 content = await storage_service.get_file(flow_id=flow_id, file_name=filename)
#                 if not content:
#                     msg = f"File {filename} not found in flow {flow_id}"
#                     raise ValueError(msg)

#                 # Ensure content is base64 encoded
#                 if isinstance(content, str):
#                     content = content.encode()
#                 return base64.b64encode(content)
#             except Exception as e:
#                 msg = f"Error reading resource {uri}: {e!s}"
#                 logger.exception(msg)
#                 raise

#         # Register handlers that filter by project
#         @self.server.list_tools()
#         @handle_mcp_errors
#         async def handle_list_project_tools():
#             """Handle listing tools for this specific project."""
#             tools = []
#             try:
#                 db_service = get_db_service()
#                 async with db_service.with_session() as session:
#                     # Get flows with mcp_enabled flag set to True and in this project
#                     flows = (
#                         await session.exec(
#                             select(Flow).where(Flow.mcp_enabled == True, Flow.folder_id == self.project_id)
#                         )
#                     ).all()

#                     for flow in flows:
#                         if flow.user_id is None:
#                             continue

#                         # Use action_name if available, otherwise construct from flow name
#                         name = flow.action_name or "_".join(flow.name.lower().split())

#                         # Use action_description if available, otherwise use defaults
#                         description = flow.action_description or (
#                             flow.description if flow.description else f"Tool generated from flow: {name}"
#                         )

#                         tool = types.Tool(
#                             name=name,
#                             description=description,
#                             inputSchema=json_schema_from_flow(flow),
#                         )
#                         tools.append(tool)
#             except Exception:
#                 logger.exception("Error in listing project tools")
#                 raise
#             return tools

#         @self.server.call_tool()
#         @handle_mcp_errors
#         async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
#             """Handle tool execution requests."""
#             mcp_config = get_mcp_config()
#             if mcp_config.enable_progress_notifications is None:
#                 settings_service = get_settings_service()
#                 mcp_config.enable_progress_notifications = (
#                     settings_service.settings.mcp_server_enable_progress_notifications
#                 )

#             background_tasks = BackgroundTasks()
#             current_user = current_user_ctx.get()

#             async def execute_tool(session):
#                 # get flow id from name
#                 flow = await get_flow_snake_case(name, current_user.id, session)
#                 if not flow:
#                     msg = f"Flow with name '{name}' not found"
#                     raise ValueError(msg)
#                 flow_id = flow.id

#                 # Process inputs
#                 processed_inputs = dict(arguments)

#                 # Initial progress notification
#                 if mcp_config.enable_progress_notifications and (
#                     progress_token := server.request_context.meta.progressToken
#                 ):
#                     await server.request_context.session.send_progress_notification(
#                         progress_token=progress_token, progress=0.0, total=1.0
#                     )

#                 conversation_id = str(uuid4())
#                 input_request = InputValueRequest(
#                     input_value=processed_inputs.get("input_value", ""),
#                     components=[],
#                     type="chat",
#                     session=conversation_id,
#                 )

#                 async def send_progress_updates():
#                     if not (mcp_config.enable_progress_notifications and server.request_context.meta.progressToken):
#                         return

#                     try:
#                         progress = 0.0
#                         while True:
#                             await server.request_context.session.send_progress_notification(
#                                 progress_token=progress_token, progress=min(0.9, progress), total=1.0
#                             )
#                             progress += 0.1
#                             await asyncio.sleep(1.0)
#                     except asyncio.CancelledError:
#                         if mcp_config.enable_progress_notifications:
#                             await server.request_context.session.send_progress_notification(
#                                 progress_token=progress_token, progress=1.0, total=1.0
#                             )
#                         raise

#                 collected_results = []
#                 try:
#                     progress_task = asyncio.create_task(send_progress_updates())

#                     try:
#                         response = await build_flow_and_stream(
#                             flow_id=flow_id,
#                             inputs=input_request,
#                             background_tasks=background_tasks,
#                             current_user=current_user,
#                         )

#                         async for line in response.body_iterator:
#                             if not line:
#                                 continue
#                             try:
#                                 event_data = json.loads(line)
#                                 if event_data.get("event") == "end_vertex":
#                                     message = (
#                                         event_data.get("data", {})
#                                         .get("build_data", {})
#                                         .get("data", {})
#                                         .get("results", {})
#                                         .get("message", {})
#                                         .get("text", "")
#                                     )
#                                     if message:
#                                         collected_results.append(types.TextContent(type="text", text=str(message)))
#                             except json.JSONDecodeError:
#                                 msg = f"Failed to parse event data: {line}"
#                                 logger.warning(msg)
#                                 continue

#                         return collected_results
#                     finally:
#                         progress_task.cancel()
#                         await asyncio.wait([progress_task])
#                         if not progress_task.cancelled() and (exc := progress_task.exception()) is not None:
#                             raise exc

#                 except Exception:
#                     if mcp_config.enable_progress_notifications and (
#                         progress_token := server.request_context.meta.progressToken
#                     ):
#                         await server.request_context.session.send_progress_notification(
#                             progress_token=progress_token, progress=1.0, total=1.0
#                         )
#                     raise

#             try:
#                 return await with_db_session(execute_tool)
#             except Exception as e:
#                 msg = f"Error executing tool {name}: {e!s}"
#                 logger.exception(msg)
#                 raise

#         # Delegate other handlers to the main MCP server
#         self.server.list_prompts = server.list_prompts
#         self.server.list_resources = server.list_resources
#         self.server.read_resource = server.read_resource
#         self.server.call_tool = server.call_tool


# # Cache of project MCP servers
# project_mcp_servers = {}


# def get_project_mcp_server(project_name: str) -> ProjectMCPServer:
#     """Get or create an MCP server for a specific project."""
#     project_name = project_snake_case(project_name)
#     if project_name not in project_mcp_servers:
#         project_mcp_servers[project_name] = ProjectMCPServer(project_name)
#     return project_mcp_servers[project_name]


# @router.get("/{project_id}/sse", response_class=StreamingResponse)
# async def handle_project_sse(
#     project_id: UUID,
#     request: Request,
#     current_user: Annotated[User, Depends(get_current_active_user)],
# ):
#     """Handle SSE connections for a specific project."""
#     # Verify project exists and user has access
#     db_service = get_db_service()
#     async with db_service.with_session() as session:
#         project = (
#             await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
#         ).first()

#         if not project:
#             raise HTTPException(status_code=404, detail="Project not found")

#     # Get project-specific SSE transport and MCP server
#     # get project name from project id
#     project_name = project_snake_case(project.name)
#     sse = get_project_sse(project_name)
#     project_server = get_project_mcp_server(project_name)
#     logger.warning(f"Project MCP server initialized for project {project_name}")
#     logger.warning(f"Project MCP server Name: {project_server.server.name}")
#     # Set context variables
#     user_token = current_user_ctx.set(current_user)
#     project_token = current_project_ctx.set(project_name)

#     try:
#         async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
#             try:
#                 logger.debug("Starting SSE connection for project %s", project_id)

#                 notification_options = NotificationOptions(
#                     prompts_changed=True, resources_changed=True, tools_changed=True
#                 )
#                 init_options = project_server.server.create_initialization_options(notification_options)

#                 try:
#                     await project_server.server.run(streams[0], streams[1], init_options)
#                 except Exception:
#                     logger.exception("Error in project MCP")
#             except BrokenResourceError:
#                 logger.info("Client disconnected from project SSE connection")
#             except asyncio.CancelledError:
#                 logger.info("Project SSE connection was cancelled")
#                 raise
#             except Exception:
#                 logger.exception("Error in project MCP")
#                 raise
#     finally:
#         current_user_ctx.reset(user_token)
#         current_project_ctx.reset(project_token)

#     # return StreamingResponse(content=[], media_type="text/event-stream")


# @router.post("/{project_id}")
# async def handle_project_messages(project_id: UUID, request: Request):
#     """Handle POST messages for a project-specific MCP server."""
#     # get project name from project id
#     db_service = get_db_service()
#     async with db_service.with_session() as session:
#         project = (await session.exec(select(Folder).where(Folder.id == project_id))).first()
#         if not project:
#             raise HTTPException(status_code=404, detail="Project not found")

#     project_name = project_snake_case(project.name)
#     sse = get_project_sse(project_name)
#     try:
#         await sse.handle_post_message(request.scope, request.receive, request._send)
#     except BrokenResourceError as e:
#         logger.info("Project MCP Server disconnected for project %s", project_id)
#         raise HTTPException(status_code=404, detail=f"Project MCP Server disconnected, error: {e}") from e


# # Replace the existing list_tools handler in the MCP server
# # @server.list_tools()
# # @handle_mcp_errors
# # async def handle_list_tools_with_projects():
# #     """Handle listing tools, including those from projects."""
# #     tools = []
# #     try:
# #         db_service = get_db_service()
# #         async with db_service.with_session() as session:
# #             # Get flows with mcp_enabled flag set to True
# #             flows = (await session.exec(select(Flow).where(Flow.mcp_enabled == True))).all()

# #             for flow in flows:
# #                 if flow.user_id is None:
# #                     continue

# #                 # Use action_name if available, otherwise construct from flow name
# #                 name = flow.action_name or "_".join(flow.name.lower().split())

# #                 # Use action_description if available, otherwise use defaults
# #                 description = flow.action_description or (
# #                     flow.description if flow.description else f"Tool generated from flow: {name}"
# #                 )

# #                 tool = types.Tool(
# #                     name=name,
# #                     description=description,
# #                     inputSchema=json_schema_from_flow(flow),
# #                 )
# #                 tools.append(tool)
# #     except Exception as e:
# #         msg = f"Error in listing tools: {e!s}"
# #         logger.exception(msg)
# #         raise
# #     return tools


# @router.patch("/{project_id}", status_code=200)
# async def update_project_mcp_settings(
#     project_id: UUID,
#     settings: list[MCPSettings],
#     current_user: Annotated[User, Depends(get_current_active_user)],
# ):
#     """Update the MCP settings of all flows in a project."""
#     try:
#         db_service = get_db_service()
#         async with db_service.with_session() as session:
#             # Fetch the project first to verify it exists and belongs to the current user
#             project = (
#                 await session.exec(
#                     select(Folder)
#                     .options(selectinload(Folder.flows))
#                     .where(Folder.id == project_id, Folder.user_id == current_user.id)
#                 )
#             ).first()

#             if not project:
#                 raise HTTPException(status_code=404, detail="Project not found")

#             # Query flows in the project
#             flows = (await session.exec(select(Flow).where(Flow.folder_id == project_id))).all()
#             flows_to_update = {x.id: x for x in settings}

#             updated_flows = []
#             for flow in flows:
#                 if flow.user_id is None or flow.user_id != current_user.id:
#                     continue

#                 if flow.id in flows_to_update:
#                     settings_to_update = flows_to_update[flow.id]
#                     flow.mcp_enabled = settings_to_update.mcp_enabled
#                     flow.action_name = settings_to_update.action_name
#                     flow.action_description = settings_to_update.action_description
#                     flow.updated_at = datetime.now(timezone.utc)
#                     session.add(flow)
#                     updated_flows.append(flow)

#             await session.commit()

#             return {"message": f"Updated MCP settings for {len(updated_flows)} flows"}

#     except Exception as e:
#         msg = f"Error updating project MCP settings: {e!s}"
#         logger.exception(msg)
#         raise HTTPException(status_code=500, detail=str(e)) from e

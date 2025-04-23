import asyncio
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from anyio import BrokenResourceError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport
from sqlalchemy.orm import selectinload
from sqlmodel import select

from langflow.api.v1.mcp import (
    current_user_ctx,
    handle_mcp_errors,
    server,
)
from langflow.helpers.flow import json_schema_from_flow
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models import Flow, Folder, ProjectMCPSettingsUpdate, User
from langflow.services.deps import get_db_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp/project", tags=["mcp_projects"])

# Create a context variable to store the current project
current_project_ctx: ContextVar[UUID | None] = ContextVar("current_project_ctx", default=None)

# Create a mapping of project-specific SSE transports
project_sse_transports = {}


def get_project_sse(project_id: UUID) -> SseServerTransport:
    """Get or create an SSE transport for a specific project."""
    project_id_str = str(project_id)
    if project_id_str not in project_sse_transports:
        project_sse_transports[project_id_str] = SseServerTransport(f"/api/v1/mcp/project/{project_id_str}/")
    return project_sse_transports[project_id_str]


@router.get("/{project_id}", response_model=list[dict])
async def list_project_tools(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    *,
    mcp_enabled_only: bool = True,
):
    """List all tools in a project that are enabled for MCP."""
    tools = []
    try:
        db_service = get_db_service()
        async with db_service.with_session() as session:
            # Fetch the project first to verify it exists and belongs to the current user
            project = (
                await session.exec(
                    select(Folder)
                    .options(selectinload(Folder.flows))
                    .where(Folder.id == project_id, Folder.user_id == current_user.id)
                )
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Query flows in the project
            flows_query = select(Flow).where(Flow.folder_id == project_id)

            # Optionally filter for MCP-enabled flows only
            if mcp_enabled_only:
                flows_query = flows_query.where(Flow.mcp_enabled == True)  # noqa: E712

            flows = (await session.exec(flows_query)).all()

            for flow in flows:
                if flow.user_id is None:
                    continue

                # Format the flow name according to MCP conventions (snake_case)
                flow_name = "_".join(flow.name.lower().split())

                # Use action_name and action_description if available, otherwise use defaults
                name = flow.action_name or flow_name
                description = flow.action_description or (
                    flow.description if flow.description else f"Tool generated from flow: {flow_name}"
                )

                tool = {
                    "id": str(flow.id),
                    "name": name,
                    "description": description,
                    "inputSchema": json_schema_from_flow(flow),
                }
                tools.append(tool)

    except Exception as e:
        msg = f"Error listing project tools: {e!s}"
        logger.exception(msg)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return tools


# Project-specific MCP server instance for handling project-specific tools
class ProjectMCPServer:
    def __init__(self, project_id: UUID):
        self.project_id = project_id
        self.server = Server(f"langflow-mcp-project-{project_id}")

        # Register handlers that filter by project
        @self.server.list_tools()
        @handle_mcp_errors
        async def handle_list_project_tools():
            """Handle listing tools for this specific project."""
            tools = []
            try:
                db_service = get_db_service()
                async with db_service.with_session() as session:
                    # Get flows with mcp_enabled flag set to True and in this project
                    flows = (
                        await session.exec(
                            select(Flow).where(Flow.mcp_enabled == True, Flow.folder_id == self.project_id)  # noqa: E712
                        )
                    ).all()

                    for flow in flows:
                        if flow.user_id is None:
                            continue

                        # Use action_name if available, otherwise construct from flow name
                        name = flow.action_name or "_".join(flow.name.lower().split())

                        # Use action_description if available, otherwise use defaults
                        description = flow.action_description or (
                            flow.description if flow.description else f"Tool generated from flow: {name}"
                        )

                        tool = types.Tool(
                            name=name,
                            description=description,
                            inputSchema=json_schema_from_flow(flow),
                        )
                        tools.append(tool)
            except Exception as e:
                msg = f"Error in listing project tools: {e!s}"
                logger.exception(msg)
                raise
            return tools

        # Delegate other handlers to the main MCP server
        self.server.list_prompts = server.list_prompts
        self.server.list_resources = server.list_resources
        self.server.read_resource = server.read_resource
        self.server.call_tool = server.call_tool


# Cache of project MCP servers
project_mcp_servers = {}


def get_project_mcp_server(project_id: UUID) -> ProjectMCPServer:
    """Get or create an MCP server for a specific project."""
    if project_id not in project_mcp_servers:
        project_mcp_servers[project_id] = ProjectMCPServer(project_id)
    return project_mcp_servers[project_id]


@router.get("/{project_id}/sse", response_class=StreamingResponse)
async def handle_project_sse(
    project_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Handle SSE connections for a specific project."""
    # Verify project exists and user has access
    db_service = get_db_service()
    async with db_service.with_session() as session:
        project = (
            await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    # Get project-specific SSE transport and MCP server
    sse = get_project_sse(project_id)
    project_server = get_project_mcp_server(project_id)

    # Set context variables
    user_token = current_user_ctx.set(current_user)
    project_token = current_project_ctx.set(project_id)

    try:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            try:
                logger.debug(f"Starting SSE connection for project {project_id}")

                notification_options = NotificationOptions(
                    prompts_changed=True, resources_changed=True, tools_changed=True
                )
                init_options = project_server.server.create_initialization_options(notification_options)

                try:
                    await project_server.server.run(streams[0], streams[1], init_options)
                except Exception as exc:
                    logger.exception(f"Error in project MCP: {exc}")
            except BrokenResourceError:
                logger.info("Client disconnected from project SSE connection")
            except asyncio.CancelledError:
                logger.info("Project SSE connection was cancelled")
                raise
            except Exception as e:
                logger.exception(f"Error in project MCP: {e}")
                raise
    finally:
        current_user_ctx.reset(user_token)
        current_project_ctx.reset(project_token)

    return StreamingResponse(content=[], media_type="text/event-stream")


@router.post("/{project_id}/")
async def handle_project_messages(project_id: UUID, request: Request):
    """Handle POST messages for a project-specific MCP server."""
    sse = get_project_sse(project_id)
    try:
        await sse.handle_post_message(request.scope, request.receive, request._send)
    except BrokenResourceError as e:
        logger.info(f"Project MCP Server disconnected for project {project_id}")
        raise HTTPException(status_code=404, detail=f"Project MCP Server disconnected, error: {e}") from e


# Replace the existing list_tools handler in the MCP server
@server.list_tools()
@handle_mcp_errors
async def handle_list_tools_with_projects():
    """Handle listing tools, including those from projects."""
    tools = []
    try:
        db_service = get_db_service()
        async with db_service.with_session() as session:
            # Get flows with mcp_enabled flag set to True
            flows = (await session.exec(select(Flow).where(Flow.mcp_enabled == True))).all()  # noqa: E712

            for flow in flows:
                if flow.user_id is None:
                    continue

                # Use action_name if available, otherwise construct from flow name
                name = flow.action_name or "_".join(flow.name.lower().split())

                # Use action_description if available, otherwise use defaults
                description = flow.action_description or (
                    flow.description if flow.description else f"Tool generated from flow: {name}"
                )

                tool = types.Tool(
                    name=name,
                    description=description,
                    inputSchema=json_schema_from_flow(flow),
                )
                tools.append(tool)
    except Exception as e:
        msg = f"Error in listing tools: {e!s}"
        logger.exception(msg)
        raise
    return tools


@router.patch("/{project_id}/mcp", status_code=200)
async def update_project_mcp_settings(
    project_id: UUID,
    settings: ProjectMCPSettingsUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Update the MCP settings of all flows in a project."""
    try:
        db_service = get_db_service()
        async with db_service.with_session() as session:
            # Fetch the project first to verify it exists and belongs to the current user
            project = (
                await session.exec(
                    select(Folder)
                    .options(selectinload(Folder.flows))
                    .where(Folder.id == project_id, Folder.user_id == current_user.id)
                )
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Query flows in the project
            flows = (await session.exec(select(Flow).where(Flow.folder_id == project_id))).all()

            updated_flows = []
            for flow in flows:
                if flow.user_id is None or flow.user_id != current_user.id:
                    continue

                if settings.mcp_enabled is not None:
                    flow.mcp_enabled = settings.mcp_enabled

                if settings.set_action_names and not flow.action_name:
                    flow_name = "_".join(flow.name.lower().split())
                    flow.action_name = flow_name

                flow.updated_at = datetime.now(timezone.utc)
                session.add(flow)
                updated_flows.append(flow)

            await session.commit()

            return {"message": f"Updated MCP settings for {len(updated_flows)} flows"}

    except Exception as e:
        msg = f"Error updating project MCP settings: {e!s}"
        logger.exception(msg)
        raise HTTPException(status_code=500, detail=str(e)) from e

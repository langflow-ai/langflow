import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from mcp import types
from sqlalchemy.orm import selectinload
from sqlmodel import select

from langflow.api.v1.mcp import (
    handle_mcp_errors,
    server,
)
from langflow.helpers.flow import json_schema_from_flow
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models import Flow, Folder, ProjectMCPSettingsUpdate, User
from langflow.services.deps import get_db_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp/project", tags=["mcp_projects"])


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

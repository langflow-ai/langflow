"""HTTP API for MCP long-running job records.

Routes:
    POST   /api/v1/mcp/jobs           Create a job (typically called by the
                                       MCP-tool fork inside ``handle_call_tool``;
                                       exposed publicly for clients that want
                                       to enqueue directly).
    GET    /api/v1/mcp/jobs/{id}      Poll a job's status / progress / result.
    GET    /api/v1/mcp/jobs           List jobs (paginated, project-scoped).
    DELETE /api/v1/mcp/jobs/{id}      Cancel a pending/running job.

All routes are scoped to projects (Folders) owned by the authenticated user,
matching the access model used by ``projects_router``.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.mcp_job.model import (
    MCPJob,
    MCPJobCreate,
    MCPJobRead,
    MCPJobStatus,
)
from langflow.services.deps import get_mcp_job_executor_service

router = APIRouter(prefix="/mcp/jobs", tags=["mcp-jobs"])


async def _accessible_project_ids(session: DbSession, user_id: UUID) -> list[UUID]:
    stmt = select(Folder.id).where(Folder.user_id == user_id)
    result = await session.exec(stmt)
    return [row if isinstance(row, UUID) else row[0] for row in result.all()]


async def _load_owned_job(session: DbSession, job_id: UUID, user_id: UUID) -> MCPJob:
    job = await session.get(MCPJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    accessible = await _accessible_project_ids(session, user_id)
    if job.project_id not in accessible:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("", response_model=MCPJobRead, status_code=status.HTTP_201_CREATED)
async def create_job(
    *,
    session: DbSession,
    payload: MCPJobCreate,
    current_user: CurrentActiveUser,
) -> MCPJobRead:
    flow = await session.get(Flow, payload.flow_id)
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    if flow.folder_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Flow is not assigned to a project",
        )
    accessible = await _accessible_project_ids(session, current_user.id)
    if flow.folder_id not in accessible:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    if not flow.long_running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Flow is not configured as long_running",
        )

    tool_name = flow.action_name or flow.name
    executor = get_mcp_job_executor_service()
    job = await executor.enqueue(
        project_id=flow.folder_id,
        flow_id=flow.id,
        tool_name=tool_name,
        inputs=payload.inputs,
        created_by=current_user.id,
        callback_url=payload.callback_url,
    )
    return MCPJobRead.model_validate(job, from_attributes=True)


@router.get("/{job_id}", response_model=MCPJobRead)
async def get_job(
    *,
    session: DbSession,
    job_id: UUID,
    current_user: CurrentActiveUser,
) -> MCPJobRead:
    job = await _load_owned_job(session, job_id, current_user.id)
    return MCPJobRead.model_validate(job, from_attributes=True)


@router.get("", response_model=list[MCPJobRead])
async def list_jobs(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    project_id: Annotated[UUID | None, Query()] = None,
    flow_id: Annotated[UUID | None, Query()] = None,
    job_status: Annotated[MCPJobStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MCPJobRead]:
    accessible = await _accessible_project_ids(session, current_user.id)
    if not accessible:
        return []
    stmt = select(MCPJob).where(MCPJob.project_id.in_(accessible))
    if project_id is not None:
        if project_id not in accessible:
            return []
        stmt = stmt.where(MCPJob.project_id == project_id)
    if flow_id is not None:
        stmt = stmt.where(MCPJob.flow_id == flow_id)
    if job_status is not None:
        stmt = stmt.where(MCPJob.status == job_status)
    stmt = stmt.order_by(MCPJob.created_at.desc()).offset(offset).limit(limit)
    result = await session.exec(stmt)
    rows = result.all()
    return [MCPJobRead.model_validate(row, from_attributes=True) for row in rows]


@router.delete("/{job_id}", response_model=MCPJobRead)
async def cancel_job(
    *,
    session: DbSession,
    job_id: UUID,
    current_user: CurrentActiveUser,
) -> MCPJobRead:
    job = await _load_owned_job(session, job_id, current_user.id)
    if job.is_terminal:
        return MCPJobRead.model_validate(job, from_attributes=True)
    executor = get_mcp_job_executor_service()
    await executor.cancel(job_id)
    await session.refresh(job)
    return MCPJobRead.model_validate(job, from_attributes=True)

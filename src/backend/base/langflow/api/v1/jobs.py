from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser
from langflow.api.v1.endpoints import simple_run_flow_task
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.services.database.models.flow import Flow
from langflow.services.database.models.job.model import Job, JobRead, JobStatus
from langflow.services.deps import get_jobs_service, session_scope
from langflow.services.jobs.service import JobsService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class CreateJobRequest(BaseModel):
    """Request model for creating a job."""

    name: str | None = None
    input_request: SimplifiedAPIRequest = Field(..., description="Input request for the flow")


@router.post("/{flow_id_or_name}", response_model=str)
async def create_job(
    request: CreateJobRequest,
    user: CurrentActiveUser,
    flow: Annotated[Flow, Depends(get_flow_by_id_or_endpoint_name)],
) -> str:
    """Create a new job."""
    try:
        jobs_service = get_jobs_service()
        return await jobs_service.create_job(
            task_func=simple_run_flow_task,
            run_at=None,
            name=request.name,
            kwargs={
                "flow": flow,
                "input_request": request.input_request,
                "stream": False,
                "api_key_user": user,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: str,
    user: CurrentActiveUser,
) -> JobRead:
    """Get job information."""
    task_service: JobsService = get_jobs_service()
    task = await task_service.get_job(job_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")
    logger.info(f"Job: {task}")
    async with session_scope() as session:
        if not user.id:
            msg = "User not found"
            raise HTTPException(status_code=404, detail=msg)
        stmt = select(Job).where(Job.id == job_id, Job.user_id == user.id)
        return (await session.exec(stmt)).first()


@router.get("/", response_model=list[JobRead])
async def get_jobs(
    user: CurrentActiveUser,
    task_service: Annotated[JobsService, Depends(get_jobs_service)],
    pending: bool | None = None,
    status: JobStatus | None = None,
) -> list[JobRead]:
    """Get all tasks for the current user."""
    # Pending is an attribute of the APSJob.job_state
    # So we use the task_service to get the jobs only if pending is not None
    if pending is not None:
        jobs = await task_service.get_jobs(user_id=user.id, pending=pending, status=status)
        ids = [job.id for job in jobs]
        async with session_scope() as session:
            stmt = select(Job).where(col(Job.id).in_(ids))
            return (await session.exec(stmt)).all()
    else:
        async with session_scope() as session:
            stmt = select(Job).where(Job.user_id == user.id)
            if status is not None:
                stmt = stmt.where(Job.status == status)
            return (await session.exec(stmt)).all()


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    user: CurrentActiveUser,
    task_service: Annotated[JobsService, Depends(get_jobs_service)],
) -> bool:
    """Cancel a job."""
    success = await task_service.cancel_job(job_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return True

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from langflow.api.utils import CurrentActiveUser
from langflow.api.v1.endpoints import simple_run_flow_task
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.services.database.models.flow import Flow
from langflow.services.database.models.job.model import JobRead
from langflow.services.deps import get_task_service
from langflow.services.task.service import TaskService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class CreateJobRequest(BaseModel):
    """Request model for creating a task."""

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
        task_service = get_task_service()
        return await task_service.create_job(
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    user: CurrentActiveUser,
) -> JobRead:
    """Get task information."""
    task_service: TaskService = get_task_service()
    task = await task_service.get_job(job_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info(f"Task: {task}")
    return JobRead.model_validate(task, from_attributes=True)


@router.get("/")
async def get_jobs(
    user: CurrentActiveUser,
    task_service: Annotated[TaskService, Depends(get_task_service)],
    pending: bool | None = None,
) -> list[JobRead]:
    """Get all tasks for the current user."""
    tasks = await task_service.get_jobs(user_id=user.id, pending=pending)
    return [JobRead.model_validate(task, from_attributes=True) for task in tasks]


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    user: CurrentActiveUser,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> bool:
    """Cancel a task."""
    success = await task_service.cancel_job(job_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return True

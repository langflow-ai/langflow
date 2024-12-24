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
from langflow.services.deps import get_task_service
from langflow.services.task.service import TaskService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class CreateJobRequest(BaseModel):
    """Request model for creating a task."""

    name: str | None = None
    input_request: SimplifiedAPIRequest = Field(..., description="Input request for the flow")


class TaskResponse(BaseModel):
    """Response model for task operations."""

    id: str
    name: str
    pending: bool


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


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    user: CurrentActiveUser,
) -> TaskResponse:
    """Get task information."""
    task_service: TaskService = get_task_service()
    task = await task_service.get_job(task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info(f"Task: {task}")
    return TaskResponse.model_validate(task, from_attributes=True)


@router.get("/", response_model=list[TaskResponse])
async def get_tasks(
    user: CurrentActiveUser,
    task_service: Annotated[TaskService, Depends(get_task_service)],
    pending: bool | None = None,
) -> list[TaskResponse]:
    """Get all tasks for the current user."""
    tasks = await task_service.get_jobs(user_id=user.id, pending=pending)
    return [TaskResponse.model_validate(task, from_attributes=True) for task in tasks]


@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    user: CurrentActiveUser,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> bool:
    """Cancel a task."""
    success = await task_service.cancel_job(task_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return True

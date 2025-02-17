"""LangFlow Task API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from langflow.services.database.models.task.model import TaskCreate, TaskRead, TaskUpdate
from langflow.services.deps import get_task_orchestration_service
from langflow.services.task_orchestration.service import TaskOrchestrationService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskRead, status_code=201)
async def create_task(
    task_create: TaskCreate,
    task_orchestration_service: Annotated[TaskOrchestrationService, Depends(get_task_orchestration_service)],
):
    """Create a new task.

    The task can include an input_request that will be used when notifying subscribers.
    The flow_data will be fetched automatically using the flow_id when creating notifications.
    """
    try:
        return await task_orchestration_service.create_task(task_create)
    except Exception as e:
        logger.error(f"Error creating task: {e!s}")
        raise HTTPException(status_code=400, detail=f"Error creating task: {e!s}") from e


@router.get("/", response_model=list[TaskRead])
async def read_tasks(
    task_orchestration_service: Annotated[TaskOrchestrationService, Depends(get_task_orchestration_service)],
    skip: int = 0,
    limit: int = 100,
):
    """Get all tasks with pagination."""
    try:
        tasks = list(task_orchestration_service._tasks.values())
        return tasks[skip : skip + limit]
    except Exception as e:
        logger.error(f"Error reading tasks: {e!s}")
        raise HTTPException(status_code=500, detail=f"Error reading tasks: {e!s}") from e


@router.get("/{task_id}", response_model=TaskRead)
async def read_task(
    task_id: UUID,
    task_orchestration_service: Annotated[TaskOrchestrationService, Depends(get_task_orchestration_service)],
):
    """Get a specific task by ID."""
    try:
        return await task_orchestration_service.get_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Task not found") from e
    except Exception as e:
        logger.error(f"Error reading task: {e!s}")
        raise HTTPException(status_code=500, detail=f"Error reading task: {e!s}") from e


@router.put("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: UUID,
    task_update: TaskUpdate,
    task_orchestration_service: Annotated[TaskOrchestrationService, Depends(get_task_orchestration_service)],
):
    """Update a specific task by ID."""
    try:
        return await task_orchestration_service.update_task(task_id, task_update)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Task not found") from e
    except Exception as e:
        logger.error(f"Error updating task: {e!s}")
        raise HTTPException(status_code=500, detail=f"Error updating task: {e!s}") from e


@router.delete("/{task_id}", response_model=TaskRead)
async def delete_task(
    task_id: UUID,
    task_orchestration_service: Annotated[TaskOrchestrationService, Depends(get_task_orchestration_service)],
):
    """Delete a specific task by ID."""
    try:
        task = await task_orchestration_service.get_task(task_id)
        await task_orchestration_service.delete_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Task not found") from e
    else:
        return task

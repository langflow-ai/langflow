"""LangFlow Task API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.task.model import Task, TaskCreate, TaskRead, TaskUpdate
from langflow.services.deps import get_task_orchestration_service
from langflow.services.task_orchestration.service import TaskOrchestrationService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskRead, status_code=201)
async def create_task(
    task_create: TaskCreate,
    task_orchestration_service: Annotated[TaskOrchestrationService, Depends(get_task_orchestration_service)],
    session: DbSession,
    _current_user: CurrentActiveUser,
):
    """Create a new task.

    The task can include an input_request that will be used when notifying subscribers.
    The flow_data will be fetched automatically using the flow_id when creating notifications.
    """
    try:
        # Use the task orchestration service to create the task
        # This will handle the business logic and event publishing
        task_read = await task_orchestration_service.create_task(task_create, session)
    except Exception as e:
        logger.error(f"Error creating task: {e!s}")
        raise HTTPException(status_code=400, detail=f"Error creating task: {e!s}") from e
    return task_read


@router.get("/", response_model=list[TaskRead])
async def read_tasks(
    session: DbSession,
    _current_user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
):
    """Get all tasks with pagination."""
    try:
        # Query tasks from the database
        query = select(Task).offset(skip).limit(limit)
        result = await session.exec(query)
        tasks = result.all()
        return [TaskRead.model_validate(task) for task in tasks]
    except Exception as e:
        logger.error(f"Error reading tasks: {e!s}")
        raise HTTPException(status_code=500, detail=f"Error reading tasks: {e!s}") from e


@router.get("/{task_id}", response_model=TaskRead)
async def read_task(
    task_id: UUID,
    session: DbSession,
):
    """Get a specific task by ID."""
    try:
        # Query the task from the database
        query = select(Task).where(Task.id == task_id)
        result = await session.exec(query)
        task = result.first()

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return TaskRead.model_validate(task)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading task: {e!s}")
        raise HTTPException(status_code=500, detail=f"Error reading task: {e!s}") from e


@router.put("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: UUID,
    task_update: TaskUpdate,
    task_orchestration_service: Annotated[TaskOrchestrationService, Depends(get_task_orchestration_service)],
    session: DbSession,
):
    """Update a specific task by ID."""
    try:
        # Use the task orchestration service to update the task
        # This will handle the business logic and event publishing
        return await task_orchestration_service.update_task(task_id, task_update, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Task not found") from e
    except Exception as e:
        logger.error(f"Error updating task: {e!s}")
        raise HTTPException(status_code=500, detail=f"Error updating task: {e!s}") from e


@router.delete("/{task_id}", response_model=TaskRead)
async def delete_task(
    task_id: UUID,
    task_orchestration_service: Annotated[TaskOrchestrationService, Depends(get_task_orchestration_service)],
    session: DbSession,
):
    """Delete a specific task by ID."""
    try:
        # Query the task from the database first to return it after deletion
        query = select(Task).where(Task.id == task_id)
        result = await session.exec(query)
        task = result.first()

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Use the task orchestration service to delete the task
        # This will handle the business logic and event publishing
        await task_orchestration_service.delete_task(task_id, session)

        return TaskRead.model_validate(task)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task: {e!s}")
        raise HTTPException(status_code=500, detail=f"Error deleting task: {e!s}") from e

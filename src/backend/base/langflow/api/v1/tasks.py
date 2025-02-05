import contextlib
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.task.model import Task, TaskCreate, TaskRead, TaskUpdate
from langflow.services.deps import get_session, get_task_orchestration_service
from langflow.services.task_orchestration.service import TaskOrchestrationService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskRead, status_code=201)
async def create_task(
    task_create: TaskCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    task_orchestration_service: Annotated[TaskOrchestrationService, Depends(get_task_orchestration_service)],
):
    """Create a new task.

    The task can include an input_request that will be used when notifying subscribers.
    The flow_data will be fetched automatically using the flow_id when creating notifications.
    """
    try:
        return await task_orchestration_service.create_task(task_create)
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating task: {e!s}")
        raise HTTPException(status_code=400, detail=f"Error creating task: {e!s}") from e


@router.get("/", response_model=list[TaskRead])
async def read_tasks(
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
):
    result = await session.execute(select(Task).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskRead)
async def read_task(
    task_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.get(Task, task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.put("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: UUID,
    task_update: TaskUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    task_orchestration_service: Annotated[TaskOrchestrationService, Depends(get_task_orchestration_service)],
):
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    task_data = task_update.model_dump(exclude_unset=True)
    for key, value in task_data.items():
        setattr(task, key, value)

    session.add(task)
    await session.commit()
    await session.refresh(task)

    # Attempt to re-orchestrate the task after update, but continue if it fails
    with contextlib.suppress(Exception):
        await task_orchestration_service.orchestrate_task(task)

    return task


@router.delete("/{task_id}", response_model=TaskRead)
async def delete_task(
    task_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await session.delete(task)
    await session.commit()
    return task

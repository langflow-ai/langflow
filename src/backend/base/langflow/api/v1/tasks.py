from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from langflow.services.database.models.task.model import TaskCreate, TaskRead, TaskUpdate
from langflow.services.deps import get_task_orchestration_service

if TYPE_CHECKING:
    from langflow.services.task_orchestration.service import TaskOrchestrationService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskRead)
async def create_task(
    task_create: TaskCreate,
    task_orchestration_service: "TaskOrchestrationService" = Depends(get_task_orchestration_service),
):
    try:
        task = task_orchestration_service.create_task(task_create)
        return task
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: UUID,
    task_orchestration_service: "TaskOrchestrationService" = Depends(get_task_orchestration_service),
):
    try:
        task = task_orchestration_service.get_task(task_id)
        return task
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: UUID,
    task_update: TaskUpdate,
    task_orchestration_service: "TaskOrchestrationService" = Depends(get_task_orchestration_service),
):
    try:
        task = task_orchestration_service.update_task(task_id, task_update)
        return task
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

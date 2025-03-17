"""API router for scheduler."""

from uuid import UUID

from fastapi import APIRouter, Depends

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.scheduler import (
    SchedulerCreate,
    SchedulerRead,
    SchedulerUpdate,
)
from langflow.services.deps import get_scheduler_service
from langflow.services.scheduler.service import SchedulerService

# build router
router = APIRouter(prefix="/schedulers", tags=["Schedulers"])


@router.post("/", response_model=SchedulerRead, status_code=201)
async def create_scheduler(
    *,
    session: DbSession,
    scheduler: SchedulerCreate,
    current_user: CurrentActiveUser,
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """Create a new scheduler."""
    return await scheduler_service.create_scheduler(
        session=session, scheduler=scheduler
    )


@router.get("/{scheduler_id}", response_model=SchedulerRead, status_code=200)
async def read_scheduler(
    *,
    session: DbSession,
    scheduler_id: UUID,
    current_user: CurrentActiveUser,
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """Get a scheduler by ID."""
    return await scheduler_service.get_scheduler(
        session=session, scheduler_id=scheduler_id
    )


@router.get("/", response_model=list[SchedulerRead], status_code=200)
async def read_schedulers(
    *,
    session: DbSession,
    flow_id: UUID | None = None,
    current_user: CurrentActiveUser,
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """Get all schedulers, optionally filtered by flow_id."""
    return await scheduler_service.get_schedulers(session=session, flow_id=flow_id)


@router.patch("/{scheduler_id}", response_model=SchedulerRead, status_code=200)
async def update_scheduler(
    *,
    session: DbSession,
    scheduler_id: UUID,
    scheduler: SchedulerUpdate,
    current_user: CurrentActiveUser,
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """Update a scheduler."""
    return await scheduler_service.update_scheduler(
        session=session, scheduler_id=scheduler_id, scheduler=scheduler
    )


@router.delete("/{scheduler_id}", status_code=204)
async def delete_scheduler(
    *,
    session: DbSession,
    scheduler_id: UUID,
    current_user: CurrentActiveUser,
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """Delete a scheduler."""
    await scheduler_service.delete_scheduler(session=session, scheduler_id=scheduler_id)


@router.get("/status", status_code=200)
async def get_scheduler_status(
    *,
    current_user: CurrentActiveUser,
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """Get the status of the scheduler service and all scheduled jobs."""
    return await scheduler_service.get_scheduler_status()


@router.get("/next-runs", status_code=200)
async def get_next_run_times(
    *,
    session: DbSession,
    flow_id: UUID | None = None,
    current_user: CurrentActiveUser,
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """Get the next run times for all scheduled jobs, optionally filtered by flow_id."""
    return await scheduler_service.get_next_run_times(session=session, flow_id=flow_id)

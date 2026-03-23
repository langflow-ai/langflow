"""API router for flow schedule management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from lfx.log.logger import logger

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.schedule.crud import (
    create_schedule,
    delete_schedule,
    get_schedule_by_flow_id,
    get_schedule_by_id,
    toggle_schedule,
    update_schedule,
)
from langflow.services.database.models.schedule.model import (
    FlowSchedule,
    FlowScheduleCreate,
    FlowScheduleRead,
    FlowScheduleUpdate,
)
from langflow.services.deps import get_scheduler_service

router = APIRouter(prefix="/schedules", tags=["Schedules"])


async def _verify_flow_ownership(session, flow_id: UUID, user_id: UUID) -> Flow:
    """Verify that the flow exists and belongs to the user.

    Allows access when flow.user_id is None (no ownership set, e.g. single-user mode)
    or when it matches the current user.
    """
    from sqlmodel import select

    statement = select(Flow).where(Flow.id == flow_id)
    result = await session.exec(statement)
    flow = result.first()
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    if flow.user_id is not None and flow.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this flow")
    return flow


@router.get("/{flow_id}", response_model=FlowScheduleRead)
async def get_flow_schedule(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get the schedule for a specific flow."""
    await _verify_flow_ownership(session, flow_id, current_user.id)
    schedule = await get_schedule_by_flow_id(session, flow_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found for this flow")
    return schedule


@router.post("", response_model=FlowScheduleRead, status_code=status.HTTP_201_CREATED)
async def create_flow_schedule(
    schedule_data: FlowScheduleCreate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Create a schedule for a flow."""
    await _verify_flow_ownership(session, schedule_data.flow_id, current_user.id)

    # Check if schedule already exists
    existing = await get_schedule_by_flow_id(session, schedule_data.flow_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Schedule already exists for this flow. Use PATCH to update.",
        )

    schedule = FlowSchedule(
        **schedule_data.model_dump(),
        user_id=current_user.id,
    )
    schedule = await create_schedule(session, schedule)

    # If active, register with scheduler
    if schedule.is_active:
        try:
            scheduler_service = get_scheduler_service()
            scheduler_service.add_schedule(schedule)
        except Exception:
            await logger.aexception("Failed to register schedule with APScheduler")

    return schedule


@router.patch("/{schedule_id}", response_model=FlowScheduleRead)
async def update_flow_schedule(
    schedule_id: UUID,
    schedule_data: FlowScheduleUpdate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Update an existing schedule."""
    schedule = await get_schedule_by_id(session, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    await _verify_flow_ownership(session, schedule.flow_id, current_user.id)

    update_dict = schedule_data.model_dump(exclude_none=True)
    if not update_dict:
        return schedule

    updated = await update_schedule(session, schedule_id, update_dict)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    # Update APScheduler
    try:
        scheduler_service = get_scheduler_service()
        if updated.is_active:
            scheduler_service.add_schedule(updated)
        else:
            scheduler_service.remove_schedule(updated.flow_id)
    except Exception:
        await logger.aexception("Failed to update schedule in APScheduler")

    return updated


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_schedule(
    schedule_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Delete a schedule."""
    schedule = await get_schedule_by_id(session, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    await _verify_flow_ownership(session, schedule.flow_id, current_user.id)

    # Remove from APScheduler
    try:
        scheduler_service = get_scheduler_service()
        scheduler_service.remove_schedule(schedule.flow_id)
    except Exception:
        await logger.aexception("Failed to remove schedule from APScheduler")

    await delete_schedule(session, schedule_id)


@router.patch("/{schedule_id}/toggle", response_model=FlowScheduleRead)
async def toggle_flow_schedule(
    schedule_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Toggle the active state of a schedule."""
    schedule = await get_schedule_by_id(session, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    await _verify_flow_ownership(session, schedule.flow_id, current_user.id)

    toggled = await toggle_schedule(session, schedule_id)
    if toggled is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    # Update APScheduler
    try:
        scheduler_service = get_scheduler_service()
        if toggled.is_active:
            scheduler_service.add_schedule(toggled)
        else:
            scheduler_service.remove_schedule(toggled.flow_id)
    except Exception:
        await logger.aexception("Failed to toggle schedule in APScheduler")

    return toggled

"""API endpoints for flow schedule management."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException
from lfx.log import logger
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_schedule.model import (
    FlowSchedule,
    FlowScheduleCreate,
    FlowScheduleRead,
    FlowScheduleUpdate,
)
from langflow.services.deps import get_scheduler_service

router = APIRouter(prefix="/schedules", tags=["Schedules"])


@router.get("/", response_model=list[FlowScheduleRead], status_code=200)
async def list_schedules(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: UUID | None = None,
):
    """List all schedules for the current user, optionally filtered by flow_id."""
    stmt = select(FlowSchedule).where(FlowSchedule.user_id == current_user.id)
    if flow_id is not None:
        stmt = stmt.where(FlowSchedule.flow_id == flow_id)
    schedules = (await session.exec(stmt)).all()
    return [FlowScheduleRead.model_validate(s, from_attributes=True) for s in schedules]


@router.post("/", response_model=FlowScheduleRead, status_code=201)
async def create_schedule(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    schedule_in: FlowScheduleCreate,
):
    """Create a new flow schedule."""
    # Verify the flow exists and belongs to the user
    flow = (
        await session.exec(
            select(Flow).where(Flow.id == schedule_in.flow_id, Flow.user_id == current_user.id)
        )
    ).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    now = datetime.now(timezone.utc)
    db_schedule = FlowSchedule(
        flow_id=schedule_in.flow_id,
        user_id=current_user.id,
        name=schedule_in.name,
        is_active=schedule_in.is_active,
        cron_expression=schedule_in.cron_expression,
        timezone=schedule_in.timezone,
        days_of_week=schedule_in.days_of_week,
        times_of_day=schedule_in.times_of_day,
        repeat_frequency=schedule_in.repeat_frequency,
        created_at=now,
        updated_at=now,
    )
    session.add(db_schedule)
    await session.flush()
    await session.refresh(db_schedule)

    # Register with the scheduler service
    try:
        scheduler = get_scheduler_service()
        await scheduler.add_schedule(db_schedule)
    except Exception:
        await logger.aexception("Failed to register schedule with scheduler service")

    return FlowScheduleRead.model_validate(db_schedule, from_attributes=True)


@router.get("/{schedule_id}", response_model=FlowScheduleRead, status_code=200)
async def get_schedule(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    schedule_id: UUID,
):
    """Get a specific schedule by ID."""
    schedule = (
        await session.exec(
            select(FlowSchedule).where(
                FlowSchedule.id == schedule_id,
                FlowSchedule.user_id == current_user.id,
            )
        )
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return FlowScheduleRead.model_validate(schedule, from_attributes=True)


@router.patch("/{schedule_id}", response_model=FlowScheduleRead, status_code=200)
async def update_schedule(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    schedule_id: UUID,
    schedule_in: FlowScheduleUpdate,
):
    """Update an existing flow schedule."""
    schedule = (
        await session.exec(
            select(FlowSchedule).where(
                FlowSchedule.id == schedule_id,
                FlowSchedule.user_id == current_user.id,
            )
        )
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    update_data = schedule_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(schedule, key, value)
    schedule.updated_at = datetime.now(timezone.utc)

    session.add(schedule)
    await session.flush()
    await session.refresh(schedule)

    # Update in the scheduler service
    try:
        scheduler = get_scheduler_service()
        await scheduler.update_schedule(schedule)
    except Exception:
        await logger.aexception("Failed to update schedule in scheduler service")

    return FlowScheduleRead.model_validate(schedule, from_attributes=True)


@router.delete("/{schedule_id}", status_code=200)
async def delete_schedule(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    schedule_id: UUID,
):
    """Delete a flow schedule."""
    schedule = (
        await session.exec(
            select(FlowSchedule).where(
                FlowSchedule.id == schedule_id,
                FlowSchedule.user_id == current_user.id,
            )
        )
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Remove from scheduler service
    try:
        scheduler = get_scheduler_service()
        await scheduler.remove_schedule(schedule_id)
    except Exception:
        await logger.aexception("Failed to remove schedule from scheduler service")

    await session.delete(schedule)
    await session.flush()
    return {"message": "Schedule deleted successfully"}

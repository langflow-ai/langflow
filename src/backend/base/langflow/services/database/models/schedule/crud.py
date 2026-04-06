"""CRUD operations for FlowSchedule model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

from sqlmodel import select

from langflow.services.database.models.schedule.model import FlowSchedule


async def create_schedule(db: AsyncSession, schedule: FlowSchedule) -> FlowSchedule:
    """Create a new flow schedule."""
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)
    return schedule


async def get_schedule_by_flow_id(db: AsyncSession, flow_id: UUID) -> FlowSchedule | None:
    """Get schedule for a specific flow."""
    statement = select(FlowSchedule).where(FlowSchedule.flow_id == flow_id)
    result = await db.exec(statement)
    return result.first()


async def get_schedule_by_id(db: AsyncSession, schedule_id: UUID) -> FlowSchedule | None:
    """Get schedule by its ID."""
    statement = select(FlowSchedule).where(FlowSchedule.id == schedule_id)
    result = await db.exec(statement)
    return result.first()


async def get_all_active_schedules(db: AsyncSession) -> list[FlowSchedule]:
    """Get all active schedules."""
    statement = select(FlowSchedule).where(FlowSchedule.is_active == True)  # noqa: E712
    result = await db.exec(statement)
    return list(result.all())


async def update_schedule(
    db: AsyncSession,
    schedule_id: UUID,
    data: dict,
) -> FlowSchedule | None:
    """Update a flow schedule."""
    schedule = await get_schedule_by_id(db, schedule_id)
    if schedule is None:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(schedule, key, value)
    schedule.updated_at = datetime.now(timezone.utc)
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)
    return schedule


async def delete_schedule(db: AsyncSession, schedule_id: UUID) -> bool:
    """Delete a flow schedule. Returns True if deleted."""
    schedule = await get_schedule_by_id(db, schedule_id)
    if schedule is None:
        return False
    await db.delete(schedule)
    await db.flush()
    return True


async def toggle_schedule(db: AsyncSession, schedule_id: UUID) -> FlowSchedule | None:
    """Toggle the is_active state of a schedule."""
    schedule = await get_schedule_by_id(db, schedule_id)
    if schedule is None:
        return None
    schedule.is_active = not schedule.is_active
    schedule.updated_at = datetime.now(timezone.utc)
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)
    return schedule


async def reset_retry_count(db: AsyncSession, schedule_id: UUID) -> FlowSchedule | None:
    """Reset the retry count to zero (called on successful execution or new cron trigger)."""
    schedule = await get_schedule_by_id(db, schedule_id)
    if schedule is None:
        return None
    schedule.retry_count = 0
    db.add(schedule)
    await db.flush()
    return schedule


async def increment_retry_count(db: AsyncSession, schedule_id: UUID) -> FlowSchedule | None:
    """Increment the retry count by 1. Returns the updated schedule."""
    schedule = await get_schedule_by_id(db, schedule_id)
    if schedule is None:
        return None
    schedule.retry_count += 1
    schedule.updated_at = datetime.now(timezone.utc)
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)
    return schedule


async def update_last_run(
    db: AsyncSession,
    schedule_id: UUID,
    status: str,
) -> FlowSchedule | None:
    """Update the last run timestamp and status."""
    schedule = await get_schedule_by_id(db, schedule_id)
    if schedule is None:
        return None
    schedule.last_run_at = datetime.now(timezone.utc)
    schedule.last_run_status = status
    db.add(schedule)
    await db.flush()
    return schedule

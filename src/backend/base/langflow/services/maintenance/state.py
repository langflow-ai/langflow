"""Read and update the maintenance flag without initializing the application."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, update
from sqlmodel import col, select

from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.maintenance import MAINTENANCE_ID, MaintenanceState

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

MAINTENANCE_REFUSAL = "This instance is in maintenance mode."


class MaintenanceStatus(BaseModel):
    maintenance: bool
    reason: str | None = None
    set_by: UUID | None = None
    set_at: datetime | None = None
    queued_jobs: int = 0
    running_jobs: int = 0


async def maintenance_enabled(session: AsyncSession) -> bool:
    """Read from the database on each admission so another pod's change is visible.

    Stays on plain ``execute`` so a caller holding a dedicated engine — which yields a
    plain SQLAlchemy session, not the SQLModel subclass — can ask the same question.
    """
    statement = select(MaintenanceState.enabled).where(MaintenanceState.id == MAINTENANCE_ID)
    enabled = (await session.execute(statement)).scalars().first()
    return enabled is True


async def maintenance_status(session: AsyncSession, *, include_details: bool = True) -> MaintenanceStatus:
    row = await session.get(MaintenanceState, MAINTENANCE_ID, populate_existing=True)
    counts = {}
    if include_details:
        counts = dict(
            (
                await session.exec(
                    select(Job.status, func.count())
                    .where(col(Job.status).in_((JobStatus.QUEUED, JobStatus.IN_PROGRESS)))
                    .group_by(Job.status)
                )
            ).all()
        )
    return MaintenanceStatus(
        maintenance=row.enabled if row else False,
        reason=row.reason if row else None,
        set_by=row.set_by if row and include_details else None,
        queued_jobs=counts.get(JobStatus.QUEUED, 0),
        running_jobs=counts.get(JobStatus.IN_PROGRESS, 0),
        set_at=(row.set_at if row.set_at.tzinfo else row.set_at.replace(tzinfo=timezone.utc)) if row else None,
    )


async def set_maintenance(
    session: AsyncSession, *, enabled: bool, reason: str | None = None, actor_id: UUID | None = None
) -> None:
    # The migration seeds the row so concurrent controls use one atomic UPDATE.
    result = await session.exec(
        update(MaintenanceState)
        .where(MaintenanceState.id == MAINTENANCE_ID)
        .values(enabled=enabled, reason=reason, set_by=actor_id, set_at=datetime.now(timezone.utc))
    )
    if result.rowcount != 1:
        msg = "Maintenance controls are not initialized. Apply database migrations first."
        raise RuntimeError(msg)
    await session.flush()

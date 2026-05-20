"""Data-access helpers for the ``trigger`` and ``trigger_job`` tables.

Kept intentionally narrow: only the queries that have real callers in
the API and the worker live here. Everything else stays inline in the
service that needs it, in line with the rest of the codebase.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import update
from sqlmodel import col, select

from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers.model import Trigger, TriggerJob

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


async def get_trigger(session: AsyncSession, trigger_id: UUID, user_id: UUID) -> Trigger | None:
    """Return a trigger owned by ``user_id`` or ``None``.

    The ownership filter mirrors the convention used by the flow endpoints:
    a cross-user access returns 404, not 403.
    """
    statement = select(Trigger).where(Trigger.id == trigger_id, Trigger.user_id == user_id)
    result = await session.exec(statement)
    return result.first()


async def list_triggers(
    session: AsyncSession,
    user_id: UUID,
    *,
    flow_id: UUID | None = None,
) -> list[Trigger]:
    statement = select(Trigger).where(Trigger.user_id == user_id)
    if flow_id is not None:
        statement = statement.where(Trigger.flow_id == flow_id)
    statement = statement.order_by(col(Trigger.created_at).desc())
    result = await session.exec(statement)
    return list(result.all())


async def list_trigger_jobs(
    session: AsyncSession,
    trigger_id: UUID,
    *,
    status: JobStatus | None = None,
    limit: int = 50,
) -> list[TriggerJob]:
    statement = select(TriggerJob).where(TriggerJob.trigger_id == trigger_id)
    if status is not None:
        statement = statement.where(TriggerJob.status == status)
    statement = statement.order_by(col(TriggerJob.scheduled_at).desc()).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def reset_stalled_in_progress(
    session: AsyncSession,
    *,
    older_than: datetime,
) -> int:
    """Reset ``in_progress`` trigger jobs whose ``started_at`` is older than ``older_than``.

    Called once at process startup to recover from worker crashes. Returns the
    number of rows reset, which the caller logs. Each reset job stays at its
    current ``attempt`` value so the existing retry budget still applies.
    """
    statement = (
        update(TriggerJob)
        .where(
            TriggerJob.status == JobStatus.IN_PROGRESS,
            col(TriggerJob.started_at).is_not(None),
            col(TriggerJob.started_at) < older_than,
        )
        .values(status=JobStatus.QUEUED, scheduled_at=datetime.now(timezone.utc), started_at=None)
    )
    result = await session.execute(statement)
    return result.rowcount or 0

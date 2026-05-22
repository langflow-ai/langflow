"""Data-access helpers for the ``trigger_job`` work queue.

Narrow on purpose: only the queries that have real call-sites in the
worker, the lifecycle hook, or the API live here. Anything situational
stays inline where it is used so this module does not balloon into a
generic ORM grab bag.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import update
from sqlmodel import col, select

from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers.model import TriggerJob

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def list_jobs_for_flow(
    session: AsyncSession,
    flow_id: UUID,
    *,
    component_id: str | None = None,
    status: JobStatus | None = None,
    limit: int = 50,
) -> list[TriggerJob]:
    """Return trigger_jobs scoped to a flow, optionally narrowed further.

    Ordered by ``scheduled_at`` descending so the caller naturally sees
    the most recent activity first.
    """
    statement = select(TriggerJob).where(TriggerJob.flow_id == flow_id)
    if component_id is not None:
        statement = statement.where(TriggerJob.component_id == component_id)
    if status is not None:
        statement = statement.where(TriggerJob.status == status)
    statement = statement.order_by(col(TriggerJob.scheduled_at).desc()).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def cancel_queued_jobs_for_components(
    session: AsyncSession,
    flow_id: UUID,
    component_ids: Sequence[str],
) -> int:
    """Mark all queued jobs for ``(flow_id, component_id)`` as cancelled.

    Used by the lifecycle hook when a trigger component is removed from
    a flow: we don't delete the row (history is preserved) but the
    worker stops considering it. Returns the count of rows updated.
    """
    if not component_ids:
        return 0
    now = datetime.now(timezone.utc)
    statement = (
        update(TriggerJob)
        .where(
            TriggerJob.flow_id == flow_id,
            col(TriggerJob.component_id).in_(list(component_ids)),
            TriggerJob.status == JobStatus.QUEUED,
        )
        .values(status=JobStatus.CANCELLED, finished_at=now)
    )
    result = await session.exec(statement)
    return result.rowcount or 0


async def reset_stalled_in_progress(
    session: AsyncSession,
    *,
    older_than: datetime,
) -> int:
    """Flip ``in_progress`` jobs older than ``older_than`` back to ``queued``.

    Used once at process startup to recover from worker crashes. The
    ``attempt`` counter is left alone — the prior run never finalised,
    so it should not consume the retry budget.
    """
    now = datetime.now(timezone.utc)
    statement = (
        update(TriggerJob)
        .where(
            TriggerJob.status == JobStatus.IN_PROGRESS,
            col(TriggerJob.started_at).is_not(None),
            col(TriggerJob.started_at) < older_than,
        )
        .values(status=JobStatus.QUEUED, scheduled_at=now, started_at=None)
    )
    result = await session.exec(statement)
    return result.rowcount or 0

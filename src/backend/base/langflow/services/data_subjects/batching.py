"""Bounded deletes and updates, so no statement holds a writer lock for long or exceeds bind limits."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, update
from sqlmodel import col, select

from langflow.services.database.models.jobs.model import ExecutionSignal, Job, JobCheckpoint, JobEvent
from langflow.services.database.models.traces.model import SpanTable, TraceTable

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement
    from sqlmodel.ext.asyncio.session import AsyncSession

BATCH_SIZE = 500


async def delete_batch(
    session: AsyncSession,
    model: Any,
    *where: ColumnElement[bool],
    pk: Any = None,
) -> int:
    """Delete up to ``BATCH_SIZE`` rows matching ``where``; return how many were deleted."""
    pk_column = pk if pk is not None else model.id
    ids = list((await session.exec(select(pk_column).where(*where).limit(BATCH_SIZE))).all())
    if not ids:
        return 0
    await session.exec(delete(model).where(col(pk_column).in_(ids)))
    return len(ids)


async def clear_reference_batch(session: AsyncSession, model: Any, column: Any, value: Any, *, pk: Any = None) -> int:
    """Set ``column`` to NULL on up to ``BATCH_SIZE`` rows where it equals ``value``."""
    pk_column = pk if pk is not None else model.id
    ids = list((await session.exec(select(pk_column).where(column == value).limit(BATCH_SIZE))).all())
    if not ids:
        return 0
    await session.exec(update(model).where(col(pk_column).in_(ids)).values({column.key: None}))
    return len(ids)


async def delete_job_batch(session: AsyncSession, *where: ColumnElement[bool]) -> int:
    """Delete up to ``BATCH_SIZE`` jobs and their FK-less children (events, signals, checkpoints)."""
    ids = list((await session.exec(select(Job.job_id).where(*where).limit(BATCH_SIZE))).all())
    if not ids:
        return 0
    for child in (JobEvent, ExecutionSignal, JobCheckpoint):
        await session.exec(delete(child).where(col(child.job_id).in_(ids)))
    await session.exec(delete(Job).where(col(Job.job_id).in_(ids)))
    return len(ids)


async def delete_trace_batch(session: AsyncSession, *where: ColumnElement[bool]) -> int:
    """Delete up to ``BATCH_SIZE`` traces and their spans (the span FK does not cascade in the DDL)."""
    ids = list((await session.exec(select(TraceTable.id).where(*where).limit(BATCH_SIZE))).all())
    if not ids:
        return 0
    await session.exec(delete(SpanTable).where(col(SpanTable.trace_id).in_(ids)))
    await session.exec(delete(TraceTable).where(col(TraceTable.id).in_(ids)))
    return len(ids)

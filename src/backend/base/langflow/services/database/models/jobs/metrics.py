"""Shared background-job aggregates for collection and transactional retention."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import case, union_all
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import col, func, select

from langflow.services.database.models.jobs.model import Job, JobEvent, JobMetricTotals, JobStatus, JobType

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

TOTAL_FIELDS = (
    "started",
    "completed",
    "failed_error",
    "failed_worker_lost",
    "failed_input_timeout",
    "timed_out",
    "cancelled",
)


def is_background_job():
    """Match persisted background submissions, excluding explicit sync requests.

    JSON text extraction excludes missing/null requests on SQLite and Postgres,
    while accepting empty request objects and absent/null mode values.
    """
    request = col(Job.job_metadata)["request"]
    return (
        (Job.type == JobType.WORKFLOW)
        & request.as_string().is_not(None)
        & (func.coalesce(request["mode"].as_string(), "") != "sync")
    )


def _live_counts(session: AsyncSession):
    """One aggregate shared by the collector and the batch being archived."""
    error_type = (
        col(Job.error).op("->>")("type")
        if session.get_bind().dialect.name == "postgresql"
        else func.json_extract(col(Job.error), "$.type")
    )
    error_type = func.coalesce(error_type, "")
    has_events = select(JobEvent.id).where(col(JobEvent.job_id) == Job.job_id).exists()
    conditions = (
        col(Job.status) == JobStatus.COMPLETED,
        (col(Job.status) == JobStatus.FAILED) & error_type.not_in(("worker_lost", "input_timed_out")),
        (col(Job.status) == JobStatus.FAILED) & (error_type == "worker_lost"),
        (col(Job.status) == JobStatus.FAILED) & (error_type == "input_timed_out"),
        col(Job.status) == JobStatus.TIMED_OUT,
        col(Job.status) == JobStatus.CANCELLED,
    )
    return (
        select(
            func.count().label("started"),
            *(
                func.coalesce(func.sum(case((condition, 1), else_=0)), 0).label(name)
                for name, condition in zip(TOTAL_FIELDS[1:], conditions, strict=True)
            ),
        )
        .select_from(Job)
        .where(is_background_job())
        .where((col(Job.status) != JobStatus.QUEUED) | has_events)
    )


async def terminal_counts(session: AsyncSession) -> dict[str, int]:
    """Read live and archived totals in one database snapshot.

    Separate reads can straddle a purge commit under READ COMMITTED, losing or
    double-counting the batch. UNION ALL keeps both parts in a single statement.
    Retries remain started while queued if they have durable events.
    """
    archived = select(*(getattr(JobMetricTotals, name) for name in TOTAL_FIELDS)).where(JobMetricTotals.id == 1)
    combined = union_all(_live_counts(session), archived).subquery()
    result = await session.exec(select(*(func.sum(combined.c[name]) for name in TOTAL_FIELDS)))
    return dict(zip(TOTAL_FIELDS, (int(value or 0) for value in result.one()), strict=True))


async def prepare_retention_metrics(session: AsyncSession) -> None:
    """Reserve SQLite's writer before selecting a retention batch.

    SQLite ignores FOR UPDATE. Even an insert that hits ON CONFLICT takes a
    write reservation, so concurrent sweeps cannot select and archive the same
    jobs. Postgres instead keeps its disjoint SKIP LOCKED batches.
    """
    if session.get_bind().dialect.name == "sqlite":
        await session.exec(sqlite_insert(JobMetricTotals).values(id=1).on_conflict_do_nothing(index_elements=["id"]))


async def archive_retention_metrics(session: AsyncSession, job_ids: Sequence[UUID]) -> None:
    """Add this locked batch's contributions in the caller's delete transaction.

    A failed delete rolls this update back too. The upsert adds in SQL so
    concurrent Postgres batches cannot overwrite each other's contributions.
    Call before deleting job events, which are part of the shared classifier.
    """
    result = await session.exec(_live_counts(session).where(col(Job.job_id).in_(job_ids)))
    counts = dict(zip(TOTAL_FIELDS, (int(value or 0) for value in result.one()), strict=True))
    if not counts["started"]:
        return
    insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    stmt = insert(JobMetricTotals).values(id=1, **counts)
    await session.exec(
        stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={name: getattr(JobMetricTotals, name) + getattr(stmt.excluded, name) for name in TOTAL_FIELDS},
        )
    )

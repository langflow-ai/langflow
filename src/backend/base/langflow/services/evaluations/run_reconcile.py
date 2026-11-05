"""Detect active runs whose worker is gone, so a dead pod never blocks new runs or edits."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import update
from sqlmodel import col, select

from langflow.services.database.models.evaluation import EvaluationRun
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.deps import get_settings_service
from langflow.services.jobs.service import JobService

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

WORKER_LOST_ERROR = "The server stopped while this run was in progress. Finished rows are kept."
ACTIVE_STATUSES = ("queued", "running")
# A run is committed a moment before its job row exists; never call it lost inside that window.
LAUNCH_GRACE = timedelta(seconds=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _is_lost(run: EvaluationRun, jobs: dict[Any, Job], lease_ttl_s: float) -> bool:
    job = jobs.get(run.job_id)
    if job is None:
        return _as_utc(run.created_at) < _now() - LAUNCH_GRACE
    if job.status not in (JobStatus.QUEUED, JobStatus.IN_PROGRESS):
        return True
    # A pod that died mid-run leaves its job IN_PROGRESS until some process restarts (the default
    # mode has no periodic sweep); a heartbeat older than the lease is the reliable death signal.
    return JobService.is_lease_stale(job, lease_ttl_s=lease_ttl_s)


async def reconcile_runs(session: AsyncSession, runs: list[EvaluationRun]) -> None:
    """Fail active runs whose job is gone or finished: the process that ran them stopped."""
    active = [run for run in runs if run.status in ACTIVE_STATUSES]
    if not active:
        return
    job_ids = [run.job_id for run in active if run.job_id is not None]
    jobs = {job.job_id: job for job in (await session.exec(select(Job).where(col(Job.job_id).in_(job_ids)))).all()}
    lease_ttl_s = get_settings_service().settings.background_lease_ttl_s
    lost = [run for run in active if _is_lost(run, jobs, lease_ttl_s)]
    if not lost:
        return
    await session.exec(
        update(EvaluationRun)
        .where(col(EvaluationRun.id).in_([run.id for run in lost]), col(EvaluationRun.status).in_(ACTIVE_STATUSES))
        .values(status="failed", error=WORKER_LOST_ERROR, finished_at=_now())
    )
    await session.commit()
    for run in lost:
        await session.refresh(run)


async def active_runs(session: AsyncSession, *conditions: Any) -> list[EvaluationRun]:
    """Runs matching ``conditions`` that are still really running (lost ones are failed on the way)."""
    stmt = select(EvaluationRun).where(*conditions, col(EvaluationRun.status).in_(ACTIVE_STATUSES))
    runs = list((await session.exec(stmt)).all())
    await reconcile_runs(session, runs)
    return [run for run in runs if run.status in ACTIVE_STATUSES]

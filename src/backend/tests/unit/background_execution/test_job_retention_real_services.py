"""Retention purge against the real migrations, on SQLite and Postgres.

The unit suite pins the purge semantics on the test app's database. This tier
runs the purge over the real Alembic schema on both engines, and on Postgres
pins its concurrency contract: every API worker runs the retention sweep, so a
purge that meets rows another sweep has already locked must skip them and take
the rest, rather than block behind that sweep or delete the same batch twice.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType, SignalType
from langflow.services.deps import session_scope
from sqlmodel import col, select, update

if TYPE_CHECKING:
    from langflow.services.jobs.service import JobService

pytestmark = pytest.mark.real_services

# Far older than anything another test leaves behind in a shared Postgres
# database, so a purge scoped to this age only ever sees this test's rows.
_AGE_DAYS = 3650
_WINDOW_DAYS = 3000


async def _aged_job(service: JobService, *, status: JobStatus) -> UUID:
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), job_type=JobType.WORKFLOW, user_id=uuid4())
    await service.append_event(job_id, "run_end", {"ok": True})
    await service.write_signal(job_id, SignalType.STOP)
    await service.save_checkpoint(job_id, "graph", "{}")
    stamp = datetime.now(timezone.utc) - timedelta(days=_AGE_DAYS)
    finished = None if status in {JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.SUSPENDED} else stamp
    async with session_scope() as session:
        await session.exec(
            update(Job)  # type: ignore[call-overload]
            .where(Job.job_id == job_id)
            .values(status=status, created_timestamp=stamp, finished_timestamp=finished)
        )
    return job_id


async def test_purge_on_real_migrations_removes_old_terminal_rows_only(real_services_job_service):
    service = real_services_job_service
    completed = await _aged_job(service, status=JobStatus.COMPLETED)
    timed_out = await _aged_job(service, status=JobStatus.TIMED_OUT)
    suspended = await _aged_job(service, status=JobStatus.SUSPENDED)

    while await service.purge_terminal_jobs(older_than_days=_WINDOW_DAYS, limit=100):
        pass

    for job_id in (completed, timed_out):
        assert await service.get_job_by_job_id(job_id) is None
        assert await service.read_events(job_id) == []
        assert await service.unconsumed_signals(job_id) == []
        assert await service.load_checkpoint(job_id, "graph") is None
    assert (await service.get_job_by_job_id(suspended)).status == JobStatus.SUSPENDED
    assert len(await service.read_events(suspended)) == 1


async def test_concurrent_purge_skips_rows_another_sweep_holds(real_services_job_service, real_services_db_url):
    """A second sweep takes the unlocked rows and returns instead of waiting.

    Without SKIP LOCKED the second purge would select the held rows too and then
    block on their DELETE until the first sweep committed, which is how two
    replicas sweeping one backlog end up queued behind (or deadlocked with) each
    other and double-counting the same batch.
    """
    if not real_services_db_url.startswith("postgresql"):
        pytest.skip("row locks are a Postgres contract; SQLite serializes writers instead")
    service = real_services_job_service
    held = [await _aged_job(service, status=JobStatus.COMPLETED) for _ in range(3)]
    free = [await _aged_job(service, status=JobStatus.FAILED) for _ in range(3)]

    async with session_scope() as holder:
        locked = await holder.exec(select(Job.job_id).where(col(Job.job_id).in_(held)).with_for_update())
        assert len(locked.all()) == len(held)

        deleted = await asyncio.wait_for(service.purge_terminal_jobs(older_than_days=_WINDOW_DAYS, limit=100), 10)

        assert deleted == len(free)
        assert [job_id for job_id in free if await service.get_job_by_job_id(job_id) is not None] == []

    assert await service.purge_terminal_jobs(older_than_days=_WINDOW_DAYS, limit=100) == len(held)
    assert [job_id for job_id in held if await service.get_job_by_job_id(job_id) is not None] == []

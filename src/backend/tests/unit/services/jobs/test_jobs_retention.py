"""Retention: age-based purge of terminal background jobs and their child rows.

The durable job table is the scaled backend's work queue, so it grows forever
without a purge: terminal rows accumulate under the claim scan and job_events
adds a row per durable milestone. The child tables carry job_id as a plain
indexed column with NO foreign key, so nothing cascades and a purge that
forgets them leaves orphans no query will ever reach again.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import JobStatus, JobType, SignalType
from langflow.services.jobs.service import BACKGROUND_ORIGIN, BACKGROUND_ORIGIN_KEY, JobService

pytestmark = pytest.mark.usefixtures("client")

_LIVE_STATUSES = [JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.SUSPENDED]


async def _aged_job(
    service: JobService,
    *,
    status: JobStatus,
    age_days: float,
    with_children: bool = False,
    background: bool = True,
    job_type: JobType = JobType.WORKFLOW,
    created_days_ago: float | None = None,
):
    """Create a job aged ``age_days`` in the past.

    ``background`` stamps the origin marker that ``submit`` writes, which is what
    retention keys on. ``created_days_ago`` ages creation separately from the
    terminal timestamp, for the run created long ago but finished recently.
    """
    from langflow.services.database.models.jobs.model import Job
    from langflow.services.deps import session_scope
    from sqlmodel import update

    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), job_type=job_type, user_id=uuid4())
    if with_children:
        await service.append_event(job_id, "run_end", {"ok": True})
        await service.write_signal(job_id, SignalType.STOP)
        await service.save_checkpoint(job_id, "graph", "{}")
    finished = datetime.now(timezone.utc) - timedelta(days=age_days)
    created_age = created_days_ago if created_days_ago is not None else age_days
    created = datetime.now(timezone.utc) - timedelta(days=created_age)
    metadata = {BACKGROUND_ORIGIN_KEY: BACKGROUND_ORIGIN} if background else {"request": {"flow_id": "legacy"}}
    async with session_scope() as session:
        await session.exec(
            update(Job)
            .where(Job.job_id == job_id)
            .values(
                status=status,
                created_timestamp=created,
                finished_timestamp=finished if status not in _LIVE_STATUSES else None,
                job_metadata=metadata,
            )
        )
    return job_id


async def _child_counts(service: JobService, job_id) -> tuple[int, int, int]:
    events = await service.read_events(job_id)
    signals = await service.unconsumed_signals(job_id)
    checkpoint = await service.load_checkpoint(job_id, "graph")
    return len(events), len(signals), 0 if checkpoint is None else 1


async def test_purge_removes_old_terminal_jobs_and_all_their_child_rows():
    """A purged job leaves nothing behind: no events, signals, or checkpoints."""
    service = JobService()
    job_id = await _aged_job(service, status=JobStatus.COMPLETED, age_days=40, with_children=True)
    assert await _child_counts(service, job_id) == (1, 1, 1)

    deleted = await service.purge_terminal_jobs(older_than_days=30, limit=100)

    assert deleted >= 1
    assert await service.get_job_by_job_id(job_id) is None
    assert await _child_counts(service, job_id) == (0, 0, 0)


@pytest.mark.parametrize("status", _LIVE_STATUSES)
async def test_purge_never_touches_live_jobs_however_old(status):
    """QUEUED, IN_PROGRESS and SUSPENDED rows are untouchable at any age.

    A SUSPENDED run is waiting on a human who may answer next month; purging it
    would silently destroy pending work.
    """
    service = JobService()
    job_id = await _aged_job(service, status=status, age_days=400)

    await service.purge_terminal_jobs(older_than_days=1, limit=100)

    job = await service.get_job_by_job_id(job_id)
    assert job is not None
    assert job.status == status


async def test_purge_keeps_terminal_jobs_inside_the_window():
    service = JobService()
    fresh = await _aged_job(service, status=JobStatus.FAILED, age_days=2)
    old = await _aged_job(service, status=JobStatus.FAILED, age_days=90)

    await service.purge_terminal_jobs(older_than_days=30, limit=100)

    assert await service.get_job_by_job_id(fresh) is not None
    assert await service.get_job_by_job_id(old) is None


async def test_purge_respects_its_batch_limit():
    """Chunked deletes keep the transaction small; the caller loops to catch up."""
    service = JobService()
    job_ids = [await _aged_job(service, status=JobStatus.CANCELLED, age_days=60) for _ in range(3)]

    first = await service.purge_terminal_jobs(older_than_days=30, limit=2)
    assert first == 2

    second = await service.purge_terminal_jobs(older_than_days=30, limit=2)
    assert second >= 1
    assert [jid for jid in job_ids if await service.get_job_by_job_id(jid) is not None] == []


async def test_purge_is_a_noop_when_nothing_is_old_enough():
    service = JobService()
    await _aged_job(service, status=JobStatus.COMPLETED, age_days=1)

    assert await service.purge_terminal_jobs(older_than_days=30, limit=100) == 0


async def test_purge_leaves_other_job_sources_alone():
    """The job table is shared, and this setting only documents background runs.

    v1 /build writes WORKFLOW rows too, so job type cannot separate them, and
    knowledge-base ingestion keeps its run history here as well. Deleting either
    from a background retention window would destroy unrelated history.
    """
    service = JobService()
    v1_build_row = await _aged_job(service, status=JobStatus.COMPLETED, age_days=90, background=False)
    ingestion_row = await _aged_job(
        service, status=JobStatus.COMPLETED, age_days=90, background=False, job_type=JobType.INGESTION
    )
    background_row = await _aged_job(service, status=JobStatus.COMPLETED, age_days=90)

    deleted = await service.purge_terminal_jobs(older_than_days=30, limit=100)

    assert deleted >= 1
    assert await service.get_job_by_job_id(background_row) is None
    assert await service.get_job_by_job_id(v1_build_row) is not None
    assert await service.get_job_by_job_id(ingestion_row) is not None


async def test_purge_keeps_an_old_run_that_finished_recently():
    """Age is the terminal time, not creation.

    A run submitted months ago and cancelled today is one day old as far as
    retention is concerned. Measuring from creation (or falling back to it) would
    delete it the moment it was cancelled.
    """
    service = JobService()
    cancelled_today = await _aged_job(service, status=JobStatus.CANCELLED, age_days=0, created_days_ago=200)

    assert await service.purge_terminal_jobs(older_than_days=30, limit=100) == 0
    assert await service.get_job_by_job_id(cancelled_today) is not None


async def test_purge_skips_terminal_rows_with_no_finished_timestamp():
    """A terminal row with no finished time is skipped, not guessed at.

    Legacy rows predate the stamping fix, so retention leaves them rather than
    inferring an age from creation and deleting something it cannot date.
    """
    from langflow.services.database.models.jobs.model import Job
    from langflow.services.deps import session_scope
    from sqlmodel import update

    service = JobService()
    job_id = await _aged_job(service, status=JobStatus.COMPLETED, age_days=90)
    async with session_scope() as session:
        await session.exec(update(Job).where(Job.job_id == job_id).values(finished_timestamp=None))

    assert await service.purge_terminal_jobs(older_than_days=30, limit=100) == 0
    assert await service.get_job_by_job_id(job_id) is not None

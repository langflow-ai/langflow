"""The scaled claim window must not hand out QUEUED rows whose lease is still fresh.

A worker that can take a lease but never run the job (one whose secret key does
not match the API's is the realistic case) leaves a freshly-leased QUEUED row
behind on every cycle. The candidate window is read once per poll and never
re-read, so once those rows fill it every claim in the fleet fails even though
the queue is full of runnable work. These run on SQLite and Postgres because the
filter compares a timestamp column to a cutoff in SQL, and the two dialects
disagree about timezone awareness on the way back out.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.jobs.model import Job
from langflow.services.jobs.service import JobService
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel.ext.asyncio.session import AsyncSession

_TTL_S = 45.0


def _postgres_url() -> str | None:
    url = os.environ.get("LANGFLOW_TEST_POSTGRES_URL") or os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not url or "+psycopg" in url:
        return url
    return url.replace("postgresql://", "postgresql+psycopg://", 1).replace("postgres://", "postgresql+psycopg://", 1)


def _as_utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes, Postgres aware ones."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@pytest.fixture(params=["sqlite", "postgresql"])
async def job_database(request, tmp_path, monkeypatch):
    """A real, isolated job table on one dialect. No stray rows from sibling tests."""
    admin = None
    schema = f"claimwindow_{uuid4().hex}"
    if request.param == "sqlite":
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    else:
        url = _postgres_url()
        if not url:
            pytest.skip("LANGFLOW_TEST_POSTGRES_URL or LANGFLOW_TEST_DATABASE_URI is not set")
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(CreateSchema(schema))
        engine = create_async_engine(url, connect_args={"options": f"-csearch_path={schema}"})

    @asynccontextmanager
    async def session_scope():
        async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
            yield session

    monkeypatch.setattr("langflow.services.jobs.service.session_scope", session_scope)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Job.__table__.create)
        yield engine
    finally:
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
            await admin.dispose()


async def _queue_a_job(service: JobService) -> UUID:
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    return job_id


@pytest.mark.usefixtures("job_database")
async def test_lease_column_tracks_the_metadata_heartbeat_through_claim_and_release():
    service = JobService()
    job_id = await _queue_a_job(service)

    unleased = await service.get_job_by_job_id(job_id)
    assert unleased.lease_heartbeat_at is None, "a job nobody has claimed must read as claimable"

    assert await service.claim_queued_lease(job_id, owner="worker:a", lease_ttl_s=_TTL_S) is True
    leased = await service.get_job_by_job_id(job_id)
    token = (leased.job_metadata or {})["heartbeat_at"]
    assert leased.lease_heartbeat_at is not None
    # The two copies are written by one UPDATE, so they must describe one instant:
    # is_lease_stale reads the metadata token and the claim poll reads the column.
    drift = abs((_as_utc(leased.lease_heartbeat_at) - datetime.fromisoformat(token)).total_seconds())
    assert drift < 1.0, f"the typed lease and its metadata token disagree by {drift}s"

    assert await service.release_queued_lease(job_id, owner="worker:a", heartbeat_at=token) is True
    released = await service.get_job_by_job_id(job_id)
    assert released.lease_heartbeat_at is None, "a released lease must not keep the row hidden"


@pytest.mark.parametrize("candidates", [1, 3, 5])
@pytest.mark.usefixtures("job_database")
async def test_a_worker_that_leases_but_never_runs_does_not_starve_the_fleet(candidates):
    service = JobService()
    # A mis-keyed worker takes the head of the queue each cycle and then fails to
    # hydrate the request, leaving the row QUEUED under a fresh lease.
    for _ in range(candidates):
        poisoned = await _queue_a_job(service)
        assert await service.claim_queued_lease(poisoned, owner="worker:mis-keyed", lease_ttl_s=_TTL_S) is True

    runnable = await _queue_a_job(service)

    claimed = await service.claim_next_queued_lease(owner="worker:healthy", lease_ttl_s=_TTL_S, candidates=candidates)

    assert claimed == runnable, (
        "every candidate slot was filled by rows the mis-keyed worker had just leased, "
        "so a healthy worker found nothing to claim behind them"
    )


@pytest.mark.usefixtures("job_database")
async def test_a_stale_lease_returns_to_the_candidate_window():
    """The filter must hide a row for one TTL, not forever."""
    service = JobService()
    job_id = await _queue_a_job(service)
    assert await service.claim_queued_lease(job_id, owner="worker:dead", lease_ttl_s=_TTL_S) is True

    assert await service.claim_next_queued_lease(owner="worker:b", lease_ttl_s=_TTL_S, candidates=5) is None

    # The claimant died without releasing. Age its lease past the TTL.
    await _age_lease(job_id, seconds=_TTL_S * 3)

    assert await service.claim_next_queued_lease(owner="worker:b", lease_ttl_s=_TTL_S, candidates=5) == job_id


async def _age_lease(job_id: UUID, *, seconds: float) -> None:
    """Backdate BOTH copies of the lease, the way a real claim writes both."""
    from langflow.services.jobs.service import session_scope

    aged = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        job.job_metadata = {**(job.job_metadata or {}), "heartbeat_at": aged.isoformat()}
        job.lease_heartbeat_at = aged
        session.add(job)
        await session.flush()


@pytest.mark.usefixtures("job_database")
async def test_a_retry_requeue_is_claimable_at_once_not_after_a_full_ttl():
    """retry_requeue_claim keeps the dead worker's lease on purpose.

    It only runs on a lease the reconciler already found stale, so the kept
    timestamp reads as claimable and the retry starts now. Stamping a fresh
    lease there instead would silently delay every retry by one TTL.
    """
    service = JobService()
    job_id = await _queue_a_job(service)
    assert await service.claim_queued_lease(job_id, owner="worker:dead", lease_ttl_s=_TTL_S) is True
    await _age_lease(job_id, seconds=_TTL_S * 3)
    await service.update_job_metadata(job_id, {"retry_safe": True, "attempt": 1, "max_attempts": 3})
    assert await service.claim_queued_job(job_id) is True  # QUEUED -> IN_PROGRESS

    assert await service.retry_requeue_claim(job_id, expected_attempt=1) is True

    claimed = await service.claim_next_queued_lease(owner="worker:healthy", lease_ttl_s=_TTL_S, candidates=5)
    assert claimed == job_id, "a retry must not wait out a lease TTL before any worker can see it"

"""Unit tests for the trigger worker's claim and finalize functions.

These cover the most novel logic in isolation, using the in-memory
SQLite session from ``conftest.async_session``. The dispatch step
(``_dispatch``) is exercised indirectly — its sub-steps are tested
here individually; a full end-to-end run against ``simple_run_flow``
is in the manual test guide (``docs/triggers/TESTING.md``).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers import Trigger, TriggerJob, TriggerType
from langflow.services.database.models.user.model import User
from langflow.services.triggers import worker as worker_module


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _seed_user_and_flow(session) -> tuple[User, Flow]:
    user = User(
        id=uuid4(),
        username=f"trig-test-{uuid4().hex[:8]}",
        password="x",  # noqa: S106 — test fixture, never read
        is_active=True,
    )
    flow = Flow(id=uuid4(), name=f"flow-{uuid4().hex[:8]}", data={}, user_id=user.id)
    session.add(user)
    session.add(flow)
    await session.commit()
    return user, flow


async def _make_trigger(session, *, user, flow, is_active: bool = True, max_attempts: int = 3) -> Trigger:
    trigger = Trigger(
        id=uuid4(),
        flow_id=flow.id,
        user_id=user.id,
        name=f"t-{uuid4().hex[:8]}",
        trigger_type=TriggerType.CRON,
        cron_expression="*/5 * * * *",
        timezone="UTC",
        payload=None,
        max_attempts=max_attempts,
        is_active=is_active,
    )
    session.add(trigger)
    await session.commit()
    return trigger


async def _enqueue_job(
    session,
    *,
    trigger: Trigger,
    scheduled_at: datetime | None = None,
    attempt: int = 1,
) -> TriggerJob:
    job = TriggerJob(
        id=uuid4(),
        trigger_id=trigger.id,
        status=JobStatus.QUEUED,
        scheduled_at=scheduled_at or _utcnow() - timedelta(seconds=1),
        attempt=attempt,
        max_attempts=trigger.max_attempts,
    )
    session.add(job)
    await session.commit()
    return job


@pytest.mark.asyncio
async def test_claim_one_picks_eligible_row(async_session):
    user, flow = await _seed_user_and_flow(async_session)
    trigger = await _make_trigger(async_session, user=user, flow=flow)
    job = await _enqueue_job(async_session, trigger=trigger)

    claimed = await worker_module._claim_one(async_session)
    await async_session.commit()

    assert claimed is not None
    assert claimed.trigger_job_id == job.id
    assert claimed.trigger_id == trigger.id

    # The claim ran via raw SQL — refresh the cached ORM object so we
    # observe the post-UPDATE row state instead of the cached pre-claim
    # value from the identity map.
    await async_session.refresh(job)
    assert job.status == JobStatus.IN_PROGRESS
    assert job.started_at is not None


@pytest.mark.asyncio
async def test_claim_one_skips_future_rows(async_session):
    user, flow = await _seed_user_and_flow(async_session)
    trigger = await _make_trigger(async_session, user=user, flow=flow)
    # A row scheduled in the future must not be claimed.
    await _enqueue_job(
        async_session,
        trigger=trigger,
        scheduled_at=_utcnow() + timedelta(hours=1),
    )

    claimed = await worker_module._claim_one(async_session)
    assert claimed is None


@pytest.mark.asyncio
async def test_claim_one_returns_none_when_queue_empty(async_session):
    user, flow = await _seed_user_and_flow(async_session)
    await _make_trigger(async_session, user=user, flow=flow)
    # No trigger_job rows at all.
    claimed = await worker_module._claim_one(async_session)
    assert claimed is None


@pytest.mark.asyncio
async def test_finalize_success_marks_completed_and_enqueues_next_for_recurring(async_session):
    user, flow = await _seed_user_and_flow(async_session)
    trigger = await _make_trigger(async_session, user=user, flow=flow)
    job = await _enqueue_job(async_session, trigger=trigger)

    claimed = worker_module._ClaimedJob(
        trigger_job_id=job.id,
        trigger_id=trigger.id,
        attempt=1,
        max_attempts=trigger.max_attempts,
    )
    run_job_id = uuid4()
    await worker_module._finalize_success(async_session, claimed, trigger, run_job_id=run_job_id)
    await async_session.commit()

    # Original row is COMPLETED and carries the run_job_id link.
    completed = (await async_session.exec(select(TriggerJob).where(TriggerJob.id == job.id))).first()
    assert completed.status == JobStatus.COMPLETED
    assert completed.run_job_id == run_job_id
    assert completed.finished_at is not None

    # Exactly one new QUEUED row is enqueued for the recurring cron.
    queued = (
        await async_session.exec(
            select(TriggerJob).where(
                TriggerJob.trigger_id == trigger.id,
                TriggerJob.status == JobStatus.QUEUED,
            ),
        )
    ).all()
    assert len(list(queued)) == 1
    assert list(queued)[0].id != job.id


@pytest.mark.asyncio
async def test_finalize_success_does_not_enqueue_for_inactive_trigger(async_session):
    user, flow = await _seed_user_and_flow(async_session)
    trigger = await _make_trigger(async_session, user=user, flow=flow, is_active=False)
    job = await _enqueue_job(async_session, trigger=trigger)

    claimed = worker_module._ClaimedJob(
        trigger_job_id=job.id,
        trigger_id=trigger.id,
        attempt=1,
        max_attempts=trigger.max_attempts,
    )
    await worker_module._finalize_success(async_session, claimed, trigger, run_job_id=uuid4())
    await async_session.commit()

    queued = (
        await async_session.exec(
            select(TriggerJob).where(
                TriggerJob.trigger_id == trigger.id,
                TriggerJob.status == JobStatus.QUEUED,
            ),
        )
    ).all()
    assert list(queued) == []


@pytest.mark.asyncio
async def test_finalize_failure_enqueues_retry_when_budget_remains(async_session):
    user, flow = await _seed_user_and_flow(async_session)
    trigger = await _make_trigger(async_session, user=user, flow=flow, max_attempts=3)
    job = await _enqueue_job(async_session, trigger=trigger, attempt=1)

    claimed = worker_module._ClaimedJob(
        trigger_job_id=job.id,
        trigger_id=trigger.id,
        attempt=1,
        max_attempts=3,
    )
    await worker_module._finalize_failure(async_session, claimed, trigger, error="boom")
    await async_session.commit()

    failed = (await async_session.exec(select(TriggerJob).where(TriggerJob.id == job.id))).first()
    assert failed.status == JobStatus.FAILED
    assert failed.error == "boom"

    retries = (
        await async_session.exec(
            select(TriggerJob).where(
                TriggerJob.trigger_id == trigger.id,
                TriggerJob.status == JobStatus.QUEUED,
            ),
        )
    ).all()
    retries = list(retries)
    assert len(retries) == 1
    assert retries[0].attempt == 2


@pytest.mark.asyncio
async def test_finalize_failure_at_max_attempts_enqueues_only_next_cron(async_session):
    """When the retry budget is exhausted, the failed row stays FAILED
    and the only queued follow-up is the next cron fire — not another
    retry of the same attempt chain."""
    user, flow = await _seed_user_and_flow(async_session)
    trigger = await _make_trigger(async_session, user=user, flow=flow, max_attempts=2)
    job = await _enqueue_job(async_session, trigger=trigger, attempt=2)

    claimed = worker_module._ClaimedJob(
        trigger_job_id=job.id,
        trigger_id=trigger.id,
        attempt=2,
        max_attempts=2,
    )
    await worker_module._finalize_failure(async_session, claimed, trigger, error="exhausted")
    await async_session.commit()

    queued = (
        await async_session.exec(
            select(TriggerJob).where(
                TriggerJob.trigger_id == trigger.id,
                TriggerJob.status == JobStatus.QUEUED,
            ),
        )
    ).all()
    queued = list(queued)
    assert len(queued) == 1
    # A retry would have ``attempt = 3``; the next cron fire is a fresh ``attempt = 1``.
    assert queued[0].attempt == 1

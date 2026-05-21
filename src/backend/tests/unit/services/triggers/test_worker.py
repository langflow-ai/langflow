"""Unit tests for the trigger worker's claim and finalize functions.

The schedule lives in ``flow.data`` now, so tests build a flow with a
CronTrigger node embedded inside its data dict, then exercise the
worker's primitives directly. The ``_dispatch`` step (which calls
``simple_run_flow``) is exercised indirectly via its sub-steps; a full
end-to-end run is covered by manual integration testing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers import TriggerJob
from langflow.services.database.models.user.model import User
from langflow.services.triggers import worker as worker_module
from langflow.services.triggers.discovery import CronTriggerConfig
from sqlmodel import select


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _cron_trigger_node(
    component_id: str = "CronTrigger-abc12",
    *,
    cron_expression: str = "*/5 * * * *",
    timezone_name: str = "UTC",
    max_attempts: int = 3,
) -> dict:
    return {
        "id": component_id,
        "type": "genericNode",
        "data": {
            "type": "CronTrigger",
            "node": {
                "template": {
                    "cron_expression": {"value": cron_expression},
                    "timezone": {"value": timezone_name},
                    "max_attempts": {"value": max_attempts},
                },
            },
        },
    }


async def _seed_user_and_flow(
    session,
    *,
    component_id: str = "CronTrigger-abc12",
    max_attempts: int = 3,
) -> tuple[User, Flow]:
    user = User(
        id=uuid4(),
        username=f"trig-{uuid4().hex[:8]}",
        password="x",  # noqa: S106 — test fixture, never read
        is_active=True,
    )
    flow = Flow(
        id=uuid4(),
        name=f"flow-{uuid4().hex[:8]}",
        data={"nodes": [_cron_trigger_node(component_id, max_attempts=max_attempts)], "edges": []},
        user_id=user.id,
    )
    session.add(user)
    session.add(flow)
    await session.commit()
    return user, flow


async def _enqueue_job(
    session,
    *,
    flow: Flow,
    component_id: str = "CronTrigger-abc12",
    scheduled_at: datetime | None = None,
    attempt: int = 1,
    max_attempts: int = 3,
) -> TriggerJob:
    job = TriggerJob(
        id=uuid4(),
        flow_id=flow.id,
        component_id=component_id,
        status=JobStatus.QUEUED,
        scheduled_at=scheduled_at or _utcnow() - timedelta(seconds=1),
        attempt=attempt,
        max_attempts=max_attempts,
    )
    session.add(job)
    await session.commit()
    return job


def _claimed_from(job: TriggerJob) -> worker_module._ClaimedJob:
    return worker_module._ClaimedJob(
        trigger_job_id=job.id,
        flow_id=job.flow_id,
        component_id=job.component_id,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
    )


def _ctx_from(flow: Flow, user: User, *, component_id: str) -> worker_module._DispatchContext:
    return worker_module._DispatchContext(
        flow=flow,
        user=user,
        config=CronTriggerConfig(
            component_id=component_id,
            cron_expression="*/5 * * * *",
            timezone="UTC",
            max_attempts=3,
        ),
    )


# --------------------------------------------------------------------------- #
#  _claim_one
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_claim_one_picks_eligible_row(async_session):
    _, flow = await _seed_user_and_flow(async_session)
    job = await _enqueue_job(async_session, flow=flow)

    claimed = await worker_module._claim_one(async_session)
    await async_session.commit()

    assert claimed is not None
    assert claimed.trigger_job_id == job.id
    assert claimed.flow_id == flow.id
    assert claimed.component_id == "CronTrigger-abc12"

    await async_session.refresh(job)
    assert job.status == JobStatus.IN_PROGRESS
    assert job.started_at is not None


@pytest.mark.asyncio
async def test_claim_one_skips_future_rows(async_session):
    _, flow = await _seed_user_and_flow(async_session)
    await _enqueue_job(async_session, flow=flow, scheduled_at=_utcnow() + timedelta(hours=1))
    assert await worker_module._claim_one(async_session) is None


@pytest.mark.asyncio
async def test_claim_one_returns_none_when_queue_empty(async_session):
    await _seed_user_and_flow(async_session)
    assert await worker_module._claim_one(async_session) is None


# --------------------------------------------------------------------------- #
#  _finalize_success
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_finalize_success_marks_completed_and_enqueues_next(async_session):
    user, flow = await _seed_user_and_flow(async_session)
    job = await _enqueue_job(async_session, flow=flow)
    claimed = _claimed_from(job)
    ctx = _ctx_from(flow, user, component_id=job.component_id)

    run_job_id = uuid4()
    await worker_module._finalize_success(async_session, claimed, ctx, run_job_id=run_job_id)
    await async_session.commit()

    await async_session.refresh(job)
    assert job.status == JobStatus.COMPLETED
    assert job.run_job_id == run_job_id
    assert job.finished_at is not None

    queued = list(
        (
            await async_session.exec(
                select(TriggerJob).where(
                    TriggerJob.flow_id == flow.id,
                    TriggerJob.component_id == claimed.component_id,
                    TriggerJob.status == JobStatus.QUEUED,
                ),
            )
        ).all()
    )
    assert len(queued) == 1
    assert queued[0].id != job.id


# --------------------------------------------------------------------------- #
#  _finalize_failure
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_finalize_failure_enqueues_retry_when_budget_remains(async_session):
    user, flow = await _seed_user_and_flow(async_session, max_attempts=3)
    job = await _enqueue_job(async_session, flow=flow, attempt=1, max_attempts=3)
    claimed = _claimed_from(job)
    ctx = _ctx_from(flow, user, component_id=job.component_id)

    await worker_module._finalize_failure(async_session, claimed, ctx, error="boom")
    await async_session.commit()

    await async_session.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.error == "boom"

    retries = list(
        (
            await async_session.exec(
                select(TriggerJob).where(
                    TriggerJob.flow_id == flow.id,
                    TriggerJob.status == JobStatus.QUEUED,
                ),
            )
        ).all()
    )
    assert len(retries) == 1
    assert retries[0].attempt == 2


@pytest.mark.asyncio
async def test_finalize_failure_at_max_attempts_enqueues_only_next_cron(async_session):
    user, flow = await _seed_user_and_flow(async_session, max_attempts=2)
    job = await _enqueue_job(async_session, flow=flow, attempt=2, max_attempts=2)
    claimed = _claimed_from(job)
    ctx = _ctx_from(flow, user, component_id=job.component_id)

    await worker_module._finalize_failure(async_session, claimed, ctx, error="exhausted")
    await async_session.commit()

    queued = list(
        (
            await async_session.exec(
                select(TriggerJob).where(
                    TriggerJob.flow_id == flow.id,
                    TriggerJob.status == JobStatus.QUEUED,
                ),
            )
        ).all()
    )
    assert len(queued) == 1
    # A retry would have attempt == 3; the next cron fire is a fresh attempt == 1.
    assert queued[0].attempt == 1


@pytest.mark.asyncio
async def test_finalize_failure_without_ctx_does_not_reschedule(async_session):
    """Trigger gone between claim and finalize → row failed, no follow-up.

    When the user deletes the component (or the entire flow) between the
    claim and the finalize step, ``_finalize_failure`` is called with
    ``ctx=None``. The row must still be marked ``failed`` but no new
    queued row should appear — there is nothing left to reschedule
    against.
    """
    _, flow = await _seed_user_and_flow(async_session)
    job = await _enqueue_job(async_session, flow=flow, attempt=3, max_attempts=3)
    claimed = _claimed_from(job)

    await worker_module._finalize_failure(async_session, claimed, ctx=None, error="trigger gone")
    await async_session.commit()

    await async_session.refresh(job)
    assert job.status == JobStatus.FAILED

    queued = list(
        (
            await async_session.exec(
                select(TriggerJob).where(
                    TriggerJob.flow_id == flow.id,
                    TriggerJob.status == JobStatus.QUEUED,
                ),
            )
        ).all()
    )
    assert queued == []


# --------------------------------------------------------------------------- #
#  _load_dispatch_context
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_load_context_resolves_flow_user_and_component(async_session):
    user, flow = await _seed_user_and_flow(async_session)
    job = await _enqueue_job(async_session, flow=flow)
    claimed = _claimed_from(job)

    ctx = await worker_module._load_dispatch_context(async_session, claimed)
    assert ctx is not None
    assert ctx.flow.id == flow.id
    assert ctx.user.id == user.id
    assert ctx.config.component_id == "CronTrigger-abc12"
    assert ctx.config.cron_expression == "*/5 * * * *"


@pytest.mark.asyncio
async def test_load_context_returns_none_when_component_was_removed(async_session):
    """User removed the CronTrigger from the flow between claim and dispatch."""
    _, flow = await _seed_user_and_flow(async_session)
    job = await _enqueue_job(async_session, flow=flow)
    claimed = _claimed_from(job)

    # Strip the component from flow.data.
    flow.data = {"nodes": [], "edges": []}
    async_session.add(flow)
    await async_session.commit()

    ctx = await worker_module._load_dispatch_context(async_session, claimed)
    assert ctx is None

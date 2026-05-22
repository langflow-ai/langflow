"""Unit tests for the flow-save lifecycle hook.

Exercises ``reconcile_trigger_jobs_for_flow`` against the in-memory
SQLite session. Covers the three reconcile outcomes (enqueue new,
cancel removed, no-op on idempotent re-save) plus the invalid-config
skip path.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers import TriggerJob
from langflow.services.database.models.user.model import User
from langflow.services.triggers.lifecycle import reconcile_trigger_jobs_for_flow
from sqlmodel import select


def _cron_node(
    component_id: str,
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


async def _seed_flow(session, *, nodes: list[dict]) -> Flow:
    user = User(
        id=uuid4(),
        username=f"trig-{uuid4().hex[:8]}",
        password="x",  # noqa: S106
        is_active=True,
    )
    flow = Flow(
        id=uuid4(),
        name=f"flow-{uuid4().hex[:8]}",
        data={"nodes": nodes, "edges": []},
        user_id=user.id,
    )
    session.add(user)
    session.add(flow)
    await session.commit()
    return flow


async def _queued_jobs(session, flow_id) -> list[TriggerJob]:
    statement = select(TriggerJob).where(
        TriggerJob.flow_id == flow_id,
        TriggerJob.status == JobStatus.QUEUED,
    )
    return list((await session.exec(statement)).all())


@pytest.mark.asyncio
async def test_enqueues_initial_job_for_new_cron_trigger(async_session):
    flow = await _seed_flow(async_session, nodes=[_cron_node("CronTrigger-a")])

    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    jobs = await _queued_jobs(async_session, flow.id)
    assert len(jobs) == 1
    assert jobs[0].component_id == "CronTrigger-a"
    assert jobs[0].attempt == 1


@pytest.mark.asyncio
async def test_idempotent_when_called_twice_with_same_state(async_session):
    flow = await _seed_flow(async_session, nodes=[_cron_node("CronTrigger-a")])

    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()
    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    jobs = await _queued_jobs(async_session, flow.id)
    assert len(jobs) == 1  # second call did not duplicate


@pytest.mark.asyncio
async def test_cancels_queued_job_when_component_is_removed(async_session):
    flow = await _seed_flow(async_session, nodes=[_cron_node("CronTrigger-a")])
    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    # User removed the node from the canvas.
    flow.data = {"nodes": [], "edges": []}
    async_session.add(flow)
    await async_session.commit()

    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    queued = await _queued_jobs(async_session, flow.id)
    assert queued == []

    cancelled = list(
        (
            await async_session.exec(
                select(TriggerJob).where(
                    TriggerJob.flow_id == flow.id,
                    TriggerJob.status == JobStatus.CANCELLED,
                ),
            )
        ).all()
    )
    assert len(cancelled) == 1
    assert cancelled[0].component_id == "CronTrigger-a"


@pytest.mark.asyncio
async def test_handles_mixed_add_and_remove_in_one_reconcile(async_session):
    flow = await _seed_flow(async_session, nodes=[_cron_node("CronTrigger-keep")])
    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    # Replace component set: keep one, drop one, add a new one.
    flow.data = {
        "nodes": [_cron_node("CronTrigger-keep"), _cron_node("CronTrigger-new")],
        "edges": [],
    }
    async_session.add(flow)
    await async_session.commit()

    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    queued = await _queued_jobs(async_session, flow.id)
    component_ids = sorted(j.component_id for j in queued)
    assert component_ids == ["CronTrigger-keep", "CronTrigger-new"]


@pytest.mark.asyncio
async def test_skips_enqueue_for_invalid_cron_expression(async_session):
    flow = await _seed_flow(
        async_session,
        nodes=[_cron_node("CronTrigger-bad", cron_expression="nonsense")],
    )

    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    queued = await _queued_jobs(async_session, flow.id)
    assert queued == []  # invalid cron silently skipped, flow save still succeeded


@pytest.mark.asyncio
async def test_skips_enqueue_for_unknown_timezone(async_session):
    flow = await _seed_flow(
        async_session,
        nodes=[_cron_node("CronTrigger-tz", timezone_name="Mars/Olympus")],
    )

    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    queued = await _queued_jobs(async_session, flow.id)
    assert queued == []


@pytest.mark.asyncio
async def test_reschedules_queued_job_when_cron_expression_changes(async_session):
    """User edits the cron in the canvas → the QUEUED row is replaced.

    Without this branch the stale ``scheduled_at`` survives until the
    next fire and the triggers page shows a "next fire in 3h" that does
    not match the cron the user just set.
    """
    flow = await _seed_flow(
        async_session,
        nodes=[_cron_node("CronTrigger-a", cron_expression="*/5 * * * *")],
    )
    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    initial = (await _queued_jobs(async_session, flow.id))[0]
    initial_scheduled_at = initial.scheduled_at
    initial_id = initial.id

    flow.data = {
        "nodes": [_cron_node("CronTrigger-a", cron_expression="*/1 * * * *")],
        "edges": [],
    }
    async_session.add(flow)
    await async_session.commit()

    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    queued = await _queued_jobs(async_session, flow.id)
    assert len(queued) == 1
    fresh = queued[0]
    assert fresh.id != initial_id  # row was rotated, not mutated
    assert fresh.scheduled_at != initial_scheduled_at  # rescheduled on new cron

    cancelled = list(
        (
            await async_session.exec(
                select(TriggerJob).where(
                    TriggerJob.flow_id == flow.id,
                    TriggerJob.status == JobStatus.CANCELLED,
                ),
            )
        ).all()
    )
    assert [j.id for j in cancelled] == [initial_id]


@pytest.mark.asyncio
async def test_reschedules_queued_job_when_timezone_changes(async_session):
    flow = await _seed_flow(
        async_session,
        nodes=[
            _cron_node(
                "CronTrigger-a",
                cron_expression="0 9 * * *",
                timezone_name="UTC",
            ),
        ],
    )
    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    initial = (await _queued_jobs(async_session, flow.id))[0]
    initial_scheduled_at = initial.scheduled_at

    flow.data = {
        "nodes": [
            _cron_node(
                "CronTrigger-a",
                cron_expression="0 9 * * *",
                timezone_name="America/Sao_Paulo",
            ),
        ],
        "edges": [],
    }
    async_session.add(flow)
    await async_session.commit()

    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    queued = await _queued_jobs(async_session, flow.id)
    assert len(queued) == 1
    assert queued[0].scheduled_at != initial_scheduled_at


@pytest.mark.asyncio
async def test_does_not_reschedule_when_only_max_attempts_changes(async_session):
    """``max_attempts`` is read live by the worker on each dispatch.

    Editing it alone must not rotate the queued row — otherwise we
    would push the next fire later than the user intends.
    """
    flow = await _seed_flow(
        async_session,
        nodes=[_cron_node("CronTrigger-a", max_attempts=3)],
    )
    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    initial = (await _queued_jobs(async_session, flow.id))[0]
    initial_id = initial.id

    flow.data = {
        "nodes": [_cron_node("CronTrigger-a", max_attempts=5)],
        "edges": [],
    }
    async_session.add(flow)
    await async_session.commit()

    await reconcile_trigger_jobs_for_flow(async_session, flow)
    await async_session.commit()

    queued = await _queued_jobs(async_session, flow.id)
    assert len(queued) == 1
    assert queued[0].id == initial_id  # untouched

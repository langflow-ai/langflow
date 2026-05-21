"""Unit tests for the read aggregator (services.triggers.queries)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers import TriggerJob
from langflow.services.database.models.user.model import User
from langflow.services.triggers.queries import list_triggers_for_user


def _cron_node(component_id: str, *, cron: str = "*/5 * * * *", tz: str = "UTC") -> dict:
    return {
        "id": component_id,
        "type": "genericNode",
        "data": {
            "type": "CronTrigger",
            "node": {
                "template": {
                    "cron_expression": {"value": cron},
                    "timezone": {"value": tz},
                    "max_attempts": {"value": 3},
                },
            },
        },
    }


async def _seed_user(session, *, suffix: str = "") -> User:
    user = User(
        id=uuid4(),
        username=f"u-{uuid4().hex[:6]}{suffix}",
        password="x",  # noqa: S106
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return user


async def _seed_flow(session, *, user_id, name: str, nodes: list[dict]) -> Flow:
    flow = Flow(id=uuid4(), name=name, data={"nodes": nodes, "edges": []}, user_id=user_id)
    session.add(flow)
    await session.commit()
    return flow


@pytest.mark.asyncio
async def test_list_returns_empty_for_user_without_triggers(async_session):
    user = await _seed_user(async_session)
    instances = await list_triggers_for_user(async_session, user.id)
    assert instances == []


@pytest.mark.asyncio
async def test_list_surfaces_one_instance_per_component(async_session):
    user = await _seed_user(async_session)
    await _seed_flow(
        async_session,
        user_id=user.id,
        name="flow-a",
        nodes=[
            _cron_node("CronTrigger-a1", cron="*/5 * * * *"),
            _cron_node("CronTrigger-a2", cron="0 9 * * *"),
        ],
    )
    await _seed_flow(
        async_session,
        user_id=user.id,
        name="flow-b",
        nodes=[_cron_node("CronTrigger-b1", cron="0 0 * * *", tz="Europe/London")],
    )

    instances = await list_triggers_for_user(async_session, user.id)
    by_id = {(i.flow_name, i.component_id): i for i in instances}
    assert set(by_id.keys()) == {
        ("flow-a", "CronTrigger-a1"),
        ("flow-a", "CronTrigger-a2"),
        ("flow-b", "CronTrigger-b1"),
    }
    london = by_id[("flow-b", "CronTrigger-b1")]
    assert london.cron_expression == "0 0 * * *"
    assert london.timezone == "Europe/London"


@pytest.mark.asyncio
async def test_list_isolates_users(async_session):
    """A user must never see another user's triggers."""
    alice = await _seed_user(async_session, suffix="a")
    bob = await _seed_user(async_session, suffix="b")
    await _seed_flow(async_session, user_id=alice.id, name="alice-flow", nodes=[_cron_node("CronTrigger-a")])
    await _seed_flow(async_session, user_id=bob.id, name="bob-flow", nodes=[_cron_node("CronTrigger-b")])

    alice_view = await list_triggers_for_user(async_session, alice.id)
    bob_view = await list_triggers_for_user(async_session, bob.id)

    assert [i.component_id for i in alice_view] == ["CronTrigger-a"]
    assert [i.component_id for i in bob_view] == ["CronTrigger-b"]


@pytest.mark.asyncio
async def test_list_picks_next_fire_from_queued_job(async_session):
    user = await _seed_user(async_session)
    flow = await _seed_flow(
        async_session,
        user_id=user.id,
        name="alpha",
        nodes=[_cron_node("CronTrigger-x")],
    )
    next_fire = datetime.now(timezone.utc) + timedelta(minutes=4)
    async_session.add(
        TriggerJob(
            id=uuid4(),
            flow_id=flow.id,
            component_id="CronTrigger-x",
            status=JobStatus.QUEUED,
            scheduled_at=next_fire,
            attempt=1,
            max_attempts=3,
        ),
    )
    await async_session.commit()

    instances = await list_triggers_for_user(async_session, user.id)
    assert len(instances) == 1
    # SQLAlchemy may strip the tz when storing into TIMESTAMP, so
    # compare the wall-clock instant tolerantly.
    assert instances[0].next_fire_at is not None
    delta = abs((instances[0].next_fire_at.replace(tzinfo=None) - next_fire.replace(tzinfo=None)).total_seconds())
    assert delta < 1


@pytest.mark.asyncio
async def test_list_picks_last_terminal_job(async_session):
    user = await _seed_user(async_session)
    flow = await _seed_flow(
        async_session,
        user_id=user.id,
        name="alpha",
        nodes=[_cron_node("CronTrigger-x")],
    )
    older = datetime.now(timezone.utc) - timedelta(hours=2)
    newer = datetime.now(timezone.utc) - timedelta(minutes=2)
    async_session.add(
        TriggerJob(
            id=uuid4(),
            flow_id=flow.id,
            component_id="CronTrigger-x",
            status=JobStatus.COMPLETED,
            scheduled_at=older,
            started_at=older,
            finished_at=older,
            attempt=1,
            max_attempts=3,
        ),
    )
    async_session.add(
        TriggerJob(
            id=uuid4(),
            flow_id=flow.id,
            component_id="CronTrigger-x",
            status=JobStatus.FAILED,
            scheduled_at=newer,
            started_at=newer,
            finished_at=newer,
            attempt=1,
            max_attempts=3,
            error="boom",
        ),
    )
    await async_session.commit()

    instances = await list_triggers_for_user(async_session, user.id)
    assert len(instances) == 1
    assert instances[0].last_finished_status == JobStatus.FAILED


@pytest.mark.asyncio
async def test_list_skips_flows_without_data(async_session):
    user = await _seed_user(async_session)
    # ``data=None`` flow — should be skipped by the server-side filter.
    flow = Flow(id=uuid4(), name="empty", data=None, user_id=user.id)
    async_session.add(flow)
    await async_session.commit()
    instances = await list_triggers_for_user(async_session, user.id)
    assert instances == []

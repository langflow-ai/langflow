"""Concurrent manual replay must retain every accepted request as a distinct event."""

import asyncio
from uuid import uuid4

import pytest
from alembic import command
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.user.model import User
from langflow.services.triggers import ledger
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from tests.unit.alembic.test_migration_execution import _make_alembic_cfg, db_url  # noqa: F401


@pytest.fixture
def migrated_ledger_url(db_url):  # noqa: F811
    command.upgrade(_make_alembic_cfg(db_url), "b7c4e1a9d3f2")  # pragma: allowlist secret
    return db_url


@pytest.mark.no_blockbuster
async def test_concurrent_replays_append_distinct_linked_rows(migrated_ledger_url, monkeypatch):
    """Hold each request before its insert so all requests observe the same ledger."""
    engine = create_async_engine(migrated_ledger_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            owner = User(username=f"replay-owner-{uuid4().hex}", password=str(uuid4()), is_active=True)
            session.add(owner)
            await session.flush()
            flow = Flow(name="Replay flow", user_id=owner.id)
            session.add(flow)
            await session.flush()
            trigger = Trigger(flow_id=flow.id, user_id=owner.id, name="Replay trigger", kind="schedule")
            session.add(trigger)
            await session.flush()
            original, _ = await ledger.append_event(
                session, trigger_id=trigger.id, dedupe_key="original", payload={"hello": "world"}
            )
            original.state = "completed"
            await session.commit()
            trigger_id, original_id = trigger.id, original.id

        append = ledger.append_event
        request_count = 4
        arrived = 0
        ready = asyncio.Event()
        write_lock = asyncio.Lock()

        async def coordinated_append(session, **kwargs):
            nonlocal arrived
            # End each read transaction before writing, allowing the same
            # deterministic schedule on SQLite and PostgreSQL. The production
            # code has already chosen the dedupe key at this point.
            await session.commit()
            arrived += 1
            if arrived == request_count:
                ready.set()
            await asyncio.wait_for(ready.wait(), timeout=10)
            async with write_lock:
                result = await append(session, **kwargs)
                await session.commit()
                return result

        monkeypatch.setattr(ledger, "append_event", coordinated_append)

        async def replay():
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await ledger.replay_event(
                    session, trigger_id=trigger_id, event_id=original_id, replay_window_days=7
                )

        replays = await asyncio.gather(*(replay() for _ in range(request_count)))
        assert len({row.id for row in replays}) == request_count
        assert len({row.dedupe_key for row in replays}) == request_count
        assert all(row.replay_of_event_id == original_id for row in replays)
        assert all(row.state == "pending" and row.payload == {"hello": "world"} for row in replays)
        async with AsyncSession(engine) as session:
            rows = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
            assert len(rows) == request_count + 1
            original = await session.get(TriggerEvent, original_id)
            assert original.state == "completed"
            assert original.payload == {"hello": "world"}
            assert original.replay_of_event_id is None
    finally:
        await engine.dispose()


@pytest.mark.no_blockbuster
async def test_append_and_dedupe_remain_in_the_callers_transaction(migrated_ledger_url):
    engine = create_async_engine(migrated_ledger_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            owner = User(username=f"rollback-owner-{uuid4().hex}", password=str(uuid4()), is_active=True)
            session.add(owner)
            await session.flush()
            flow = Flow(name="Rollback flow", user_id=owner.id)
            session.add(flow)
            await session.flush()
            trigger = Trigger(flow_id=flow.id, user_id=owner.id, name="Original", kind="schedule")
            session.add(trigger)
            await session.flush()
            original, _ = await ledger.append_event(session, trigger_id=trigger.id, dedupe_key="original")
            await session.commit()
            trigger_id, original_id = trigger.id, original.id

        async with AsyncSession(engine, expire_on_commit=False) as session:
            # A SELECT does not begin a DBAPI transaction in SQLite's legacy mode.
            trigger = await session.get(Trigger, trigger_id)
            first, created = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="first")
            assert created
            duplicate, created = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="original")
            assert not created
            assert duplicate.id == original_id
            second, created = await ledger.append_event(session, trigger_id=trigger_id, dedupe_key="second")
            assert created
            trigger.name = "Must roll back"
            await session.flush()
            first_id, second_id = first.id, second.id
            await session.rollback()

        async with AsyncSession(engine) as session:
            assert await session.get(TriggerEvent, first_id) is None
            assert await session.get(TriggerEvent, second_id) is None
            assert await session.get(TriggerEvent, original_id) is not None
            assert (await session.get(Trigger, trigger_id)).name == "Original"
    finally:
        await engine.dispose()

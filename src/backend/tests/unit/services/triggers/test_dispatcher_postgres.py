"""Exercise replica capacity checks against real PostgreSQL row locks."""

import asyncio
import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.database.models.user.model import User
from langflow.services.triggers import dispatcher
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from tests.unit.alembic.test_migration_execution import (
    _create_pg_test_database,
    _drop_pg_test_database,
    _normalize_pg_url,
)

pytestmark = pytest.mark.no_blockbuster


async def test_postgres_replicas_share_one_trigger_capacity(monkeypatch):
    url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not url:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI is required")
    base_url = _normalize_pg_url(url)
    database = f"trigger_capacity_{uuid4().hex}"
    test_url = _create_pg_test_database(base_url, database)
    engine = create_async_engine(test_url)

    @asynccontextmanager
    async def scope():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
            await session.commit()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        async with scope() as session:
            user = User(username=f"replica-{uuid4().hex}", password=str(uuid4()), is_active=True)
            session.add(user)
            await session.flush()
            flow = Flow(name="Concurrent claims", user_id=user.id)
            session.add(flow)
            await session.flush()
            trigger = Trigger(flow_id=flow.id, user_id=user.id, kind="schedule", name="One slot", concurrency_limit=1)
            session.add(trigger)
            await session.flush()
            trigger_id = trigger.id
            session.add_all([TriggerEvent(trigger_id=trigger_id, dedupe_key=str(index)) for index in range(20)])
        monkeypatch.setattr(dispatcher, "session_scope", scope)

        async def claim(owner):
            async with scope() as session:
                return await dispatcher.claim_batch(session, owner=owner, limit=10, lease_ttl_s=60)

        batches = await asyncio.gather(*(claim(f"replica-{index}") for index in range(4)))
        assert sum(map(len, batches)) == 1
        async with scope() as session:
            rows = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
            assert sum(row.state == "claimed" for row in rows) == 1
    finally:
        await engine.dispose()
        _drop_pg_test_database(base_url, database)

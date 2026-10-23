"""Tests for the WorkerRegistry model against a real in-memory SQLite database."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.worker_registry import WorkerRegistry, WorkerState
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession


def _as_utc(value: datetime) -> datetime:
    """Attach UTC to a tz-naive datetime read back from SQLite."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@pytest.fixture(name="registry_db_engine")
def registry_db_engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    yield engine
    engine.sync_engine.dispose()


@pytest.fixture(name="registry_async_session")
async def registry_async_session(registry_db_engine):
    from sqlmodel import SQLModel

    async with registry_db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(registry_db_engine, expire_on_commit=False) as session:
        yield session
    async with registry_db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await registry_db_engine.dispose()


async def test_worker_registry_round_trips(registry_async_session: AsyncSession):
    started_at = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc)
    last_heartbeat = datetime(2026, 6, 5, 12, 0, 30, tzinfo=timezone.utc)
    job_id = uuid4()
    worker = WorkerRegistry(
        owner="worker:1234:abcd",
        pid=1234,
        host="worker-host-1",
        started_at=started_at,
        last_heartbeat=last_heartbeat,
        state=WorkerState.BUSY,
        current_job_id=job_id,
    )
    registry_async_session.add(worker)
    await registry_async_session.commit()
    registry_async_session.expunge_all()

    stored = await registry_async_session.get(WorkerRegistry, "worker:1234:abcd")
    assert stored is not None
    assert stored.owner == "worker:1234:abcd"
    assert stored.pid == 1234
    assert stored.host == "worker-host-1"
    # SQLite stores tz-aware datetimes as naive strings, so normalize before
    # comparing the instant. The persisted value (UTC) round-trips intact.
    assert _as_utc(stored.started_at) == started_at
    assert _as_utc(stored.last_heartbeat) == last_heartbeat
    assert stored.state == WorkerState.BUSY
    assert stored.current_job_id == job_id


async def test_current_job_id_is_optional(registry_async_session: AsyncSession):
    worker = WorkerRegistry(
        owner="worker:5678:efgh",
        pid=5678,
        host="worker-host-2",
        started_at=datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc),
        last_heartbeat=datetime(2026, 6, 5, 12, 0, 5, tzinfo=timezone.utc),
        state=WorkerState.IDLE,
        current_job_id=None,
    )
    registry_async_session.add(worker)
    await registry_async_session.commit()
    registry_async_session.expunge_all()

    stored = await registry_async_session.get(WorkerRegistry, "worker:5678:efgh")
    assert stored is not None
    assert stored.state == WorkerState.IDLE
    assert stored.current_job_id is None


async def test_owner_is_primary_key(registry_async_session: AsyncSession):
    now = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc)
    first = WorkerRegistry(
        owner="worker:9999:dup",
        pid=9999,
        host="host-a",
        started_at=now,
        last_heartbeat=now,
        state=WorkerState.IDLE,
    )
    registry_async_session.add(first)
    await registry_async_session.commit()

    duplicate = WorkerRegistry(
        owner="worker:9999:dup",
        pid=10000,
        host="host-b",
        started_at=now,
        last_heartbeat=now,
        state=WorkerState.BUSY,
    )
    registry_async_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await registry_async_session.commit()

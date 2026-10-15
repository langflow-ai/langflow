"""WorkerRegistryService CRUD + aggregate queries over the real worker_registry table.

These run against the REAL test DB (the ``client`` fixture; SQLite locally,
Postgres in CI) with NO mocking. Timestamps are injected so freshness /
staleness math is deterministic and never races the wall clock.

``count_by_state`` and ``prune_stale`` use the same dialect-aware ``last_heartbeat``
cutoff the metrics collector uses (aware cutoff on Postgres, naive-UTC on SQLite)
so boundary rows are not silently dropped on either dialect.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.background_execution.worker_registry import WorkerRegistryService
from langflow.services.database.models.worker_registry.model import WorkerRegistry, WorkerState
from langflow.services.deps import session_scope
from sqlmodel import func, select

pytestmark = pytest.mark.usefixtures("client")


def _aware(dt: datetime) -> datetime:
    """Normalize a possibly-naive stored datetime to aware UTC (SQLite hands back naive)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def test_register_creates_one_idle_row():
    """Register inserts exactly one IDLE row with started_at/last_heartbeat set and no job."""
    service = WorkerRegistryService()
    owner = "worker:1:abc"

    async with session_scope() as session:
        await service.register(session, owner=owner, pid=111, host="host-a")

    async with session_scope() as session:
        row = await session.get(WorkerRegistry, owner)
        assert row is not None
        assert row.pid == 111
        assert row.host == "host-a"
        assert row.state == WorkerState.IDLE
        assert row.current_job_id is None
        assert row.started_at is not None
        assert row.last_heartbeat is not None


async def test_reregister_same_owner_is_idempotent_upsert():
    """Re-registering the SAME owner does not raise and updates pid/host/started_at/state."""
    service = WorkerRegistryService()
    owner = "worker:2:abc"

    async with session_scope() as session:
        await service.register(session, owner=owner, pid=200, host="host-old")

    async with session_scope() as session:
        first = await session.get(WorkerRegistry, owner)
        first_started = _aware(first.started_at)

    # Drive it busy so we can prove re-register resets to IDLE.
    async with session_scope() as session:
        await service.heartbeat(session, owner=owner, state=WorkerState.BUSY, current_job_id=uuid4())

    # Re-register with new pid/host (no IntegrityError on the existing PK).
    async with session_scope() as session:
        await service.register(session, owner=owner, pid=201, host="host-new")

    async with session_scope() as session:
        count = (await session.exec(select(func.count()).select_from(WorkerRegistry))).one()
        assert int(count) == 1
        row = await session.get(WorkerRegistry, owner)
        assert row.pid == 201
        assert row.host == "host-new"
        assert row.state == WorkerState.IDLE
        assert row.current_job_id is None
        assert _aware(row.started_at) >= first_started


async def test_heartbeat_updates_state_job_and_advances_last_heartbeat():
    """Heartbeat flips state -> BUSY + current_job_id, and last_heartbeat advances."""
    service = WorkerRegistryService()
    owner = "worker:3:abc"

    async with session_scope() as session:
        await service.register(session, owner=owner, pid=300, host="host-c")

    async with session_scope() as session:
        before = _aware((await session.get(WorkerRegistry, owner)).last_heartbeat)

    job_id = uuid4()
    async with session_scope() as session:
        await service.heartbeat(session, owner=owner, state=WorkerState.BUSY, current_job_id=job_id)

    async with session_scope() as session:
        row = await session.get(WorkerRegistry, owner)
        assert row.state == WorkerState.BUSY
        assert row.current_job_id == job_id
        assert _aware(row.last_heartbeat) >= before


async def test_heartbeat_on_missing_owner_recreates_row():
    """Heartbeat on an owner with no row recreates it (robust against a pruned row)."""
    service = WorkerRegistryService()
    owner = "worker:4:abc"
    job_id = uuid4()

    async with session_scope() as session:
        await service.heartbeat(session, owner=owner, state=WorkerState.BUSY, current_job_id=job_id)

    async with session_scope() as session:
        row = await session.get(WorkerRegistry, owner)
        assert row is not None
        assert row.state == WorkerState.BUSY
        assert row.current_job_id == job_id


async def test_deregister_removes_row_and_is_noop_when_missing():
    """Deregister deletes the row; deregister of an absent owner is a no-op."""
    service = WorkerRegistryService()
    owner = "worker:5:abc"

    async with session_scope() as session:
        await service.register(session, owner=owner, pid=500, host="host-e")

    async with session_scope() as session:
        await service.deregister(session, owner=owner)

    async with session_scope() as session:
        assert await session.get(WorkerRegistry, owner) is None

    # No-op: deregistering an already-gone owner must not raise.
    async with session_scope() as session:
        await service.deregister(session, owner=owner)


async def test_count_by_state_excludes_stale_and_splits_busy_idle():
    """Seed fresh-idle, fresh-busy, and a stale row: online=2, busy=1, idle=1."""
    service = WorkerRegistryService()
    now = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc)
    online_window = timedelta(seconds=30)

    async with session_scope() as session:
        # Fresh idle: heartbeat right at now.
        session.add(
            WorkerRegistry(
                owner="fresh-idle",
                pid=1,
                host="h",
                started_at=now - timedelta(minutes=5),
                last_heartbeat=now,
                state=WorkerState.IDLE,
                current_job_id=None,
            )
        )
        # Fresh busy: heartbeat 10s ago (within window).
        session.add(
            WorkerRegistry(
                owner="fresh-busy",
                pid=2,
                host="h",
                started_at=now - timedelta(minutes=5),
                last_heartbeat=now - timedelta(seconds=10),
                state=WorkerState.BUSY,
                current_job_id=uuid4(),
            )
        )
        # Stale: heartbeat 60s ago (past the 30s window) — excluded everywhere.
        session.add(
            WorkerRegistry(
                owner="stale",
                pid=3,
                host="h",
                started_at=now - timedelta(minutes=5),
                last_heartbeat=now - timedelta(seconds=60),
                state=WorkerState.IDLE,
                current_job_id=None,
            )
        )
        await session.flush()

    async with session_scope() as session:
        counts = await service.count_by_state(session, now=now, online_window=online_window)

    assert counts == {"online": 2, "busy": 1, "idle": 1}


async def test_prune_stale_deletes_only_old_rows_and_returns_count():
    """prune_stale deletes rows older than retention and returns the deleted count."""
    service = WorkerRegistryService()
    now = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc)
    retention_s = 3600.0

    async with session_scope() as session:
        # Fresh: within retention, must survive.
        session.add(
            WorkerRegistry(
                owner="keep",
                pid=1,
                host="h",
                started_at=now - timedelta(hours=2),
                last_heartbeat=now - timedelta(seconds=10),
                state=WorkerState.IDLE,
                current_job_id=None,
            )
        )
        # Two stale rows past the 1h retention, must be deleted.
        session.add(
            WorkerRegistry(
                owner="drop-1",
                pid=2,
                host="h",
                started_at=now - timedelta(hours=3),
                last_heartbeat=now - timedelta(seconds=3700),
                state=WorkerState.IDLE,
                current_job_id=None,
            )
        )
        session.add(
            WorkerRegistry(
                owner="drop-2",
                pid=3,
                host="h",
                started_at=now - timedelta(hours=3),
                last_heartbeat=now - timedelta(hours=5),
                state=WorkerState.BUSY,
                current_job_id=uuid4(),
            )
        )
        await session.flush()

    async with session_scope() as session:
        deleted = await service.prune_stale(session, now=now, retention_s=retention_s)

    assert deleted == 2

    async with session_scope() as session:
        assert await session.get(WorkerRegistry, "keep") is not None
        assert await session.get(WorkerRegistry, "drop-1") is None
        assert await session.get(WorkerRegistry, "drop-2") is None

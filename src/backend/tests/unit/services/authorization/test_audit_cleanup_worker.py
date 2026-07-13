"""Tests for the scheduled ``authz_audit_log`` retention worker.

These cover the behaviour that the startup-only sweep lacked (gap C): the
cleanup must run repeatedly on a recurring schedule, must be a no-op when
retention is disabled (``AUTHZ_AUDIT_RETENTION_DAYS=0``) or auditing is off
(``AUTHZ_AUDIT_ENABLED=False``), and must keep best-effort semantics.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.task import audit_cleanup
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


def _svc(*, enabled: bool, retention: int, interval: int = 86400) -> SimpleNamespace:
    """A stand-in settings service exposing only the audit knobs the worker reads."""
    return SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_AUDIT_ENABLED=enabled,
            AUTHZ_AUDIT_RETENTION_DAYS=retention,
            AUTHZ_AUDIT_CLEANUP_INTERVAL=interval,
        )
    )


def _audit_row(*, days_old: int, resource_id=None) -> AuthzAuditLog:
    timestamp = datetime.now(timezone.utc) - timedelta(days=days_old)
    return AuthzAuditLog(
        user_id=uuid4(),
        action="flow:read",
        resource_type="flow",
        resource_id=resource_id or uuid4(),
        result="allow",
        details={"domain": "*"},
        timestamp=timestamp,
    )


@contextlib.asynccontextmanager
async def _fake_session_scope():
    """No-op session scope for tests that patch out the cleanup helper."""
    yield SimpleNamespace()


# --------------------------------------------------------------------------- #
# Scheduling behaviour (the core of gap C)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_worker_runs_cleanup_repeatedly_on_schedule(monkeypatch):
    """The worker invokes the retention helper repeatedly, not just once."""
    cleanup = AsyncMock(return_value=3)
    monkeypatch.setattr(audit_cleanup, "clean_authz_audit_log", cleanup)
    monkeypatch.setattr(audit_cleanup, "session_scope", _fake_session_scope)
    monkeypatch.setattr(audit_cleanup, "get_settings_service", lambda: _svc(enabled=True, retention=90))

    worker = audit_cleanup.AuditLogCleanupWorker(interval=0.03)
    await worker.start()
    assert worker._task is not None
    try:
        # Several intervals worth of wall-clock; sleep-first means the first
        # sweep lands one interval in, with more following.
        await asyncio.sleep(0.25)
    finally:
        await worker.stop()

    assert worker._task is None
    assert cleanup.call_count >= 2, f"expected recurring sweeps, got {cleanup.call_count}"


@pytest.mark.asyncio
async def test_worker_is_noop_when_retention_disabled(monkeypatch):
    """AUTHZ_AUDIT_RETENTION_DAYS=0 -> no task is scheduled and nothing is pruned."""
    cleanup = AsyncMock()
    monkeypatch.setattr(audit_cleanup, "clean_authz_audit_log", cleanup)
    monkeypatch.setattr(audit_cleanup, "session_scope", _fake_session_scope)
    monkeypatch.setattr(audit_cleanup, "get_settings_service", lambda: _svc(enabled=True, retention=0))

    worker = audit_cleanup.AuditLogCleanupWorker(interval=0.02)
    await worker.start()
    assert worker._task is None  # never scheduled
    await asyncio.sleep(0.08)
    cleanup.assert_not_called()
    await worker.stop()  # safe no-op


@pytest.mark.asyncio
async def test_worker_is_noop_when_audit_disabled(monkeypatch):
    """AUTHZ_AUDIT_ENABLED=False -> no task is scheduled and nothing is pruned."""
    cleanup = AsyncMock()
    monkeypatch.setattr(audit_cleanup, "clean_authz_audit_log", cleanup)
    monkeypatch.setattr(audit_cleanup, "session_scope", _fake_session_scope)
    monkeypatch.setattr(audit_cleanup, "get_settings_service", lambda: _svc(enabled=False, retention=90))

    worker = audit_cleanup.AuditLogCleanupWorker(interval=0.02)
    await worker.start()
    assert worker._task is None
    await asyncio.sleep(0.08)
    cleanup.assert_not_called()
    await worker.stop()


@pytest.mark.asyncio
async def test_worker_start_stop_and_idempotency(monkeypatch):
    """start()/stop() manage the task and tolerate double calls."""
    cleanup = AsyncMock()
    monkeypatch.setattr(audit_cleanup, "clean_authz_audit_log", cleanup)
    monkeypatch.setattr(audit_cleanup, "session_scope", _fake_session_scope)
    # interval read from settings (5s) so no sweep fires during the short test.
    monkeypatch.setattr(audit_cleanup, "get_settings_service", lambda: _svc(enabled=True, retention=90, interval=5))

    worker = audit_cleanup.AuditLogCleanupWorker()
    await worker.start()
    assert worker._task is not None
    assert not worker._stop_event.is_set()
    assert worker._interval == 5  # resolved from AUTHZ_AUDIT_CLEANUP_INTERVAL

    first_task = worker._task
    await worker.start()  # already running -> no-op, same task
    assert worker._task is first_task

    await worker.stop()
    assert worker._task is None
    assert worker._stop_event.is_set()
    await worker.stop()  # idempotent no-op


@pytest.mark.asyncio
async def test_worker_survives_cleanup_failure(monkeypatch):
    """A failing sweep is swallowed and the loop keeps going."""
    cleanup = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(audit_cleanup, "clean_authz_audit_log", cleanup)
    monkeypatch.setattr(audit_cleanup, "session_scope", _fake_session_scope)
    monkeypatch.setattr(audit_cleanup, "get_settings_service", lambda: _svc(enabled=True, retention=90))

    worker = audit_cleanup.AuditLogCleanupWorker(interval=0.03)
    await worker.start()
    try:
        await asyncio.sleep(0.2)
    finally:
        await worker.stop()

    # Despite every sweep raising, the worker kept scheduling more.
    assert cleanup.call_count >= 2


def test_interval_resolution_prefers_override():
    """The constructor override wins; otherwise the value comes from the setting.

    AUTHZ_AUDIT_CLEANUP_INTERVAL is a pydantic field (default 86400, ge=300), so
    the worker reads it directly without a missing/garbage fallback.
    """
    overridden = audit_cleanup.AuditLogCleanupWorker(interval=1.5)
    assert overridden._resolve_interval(SimpleNamespace(AUTHZ_AUDIT_CLEANUP_INTERVAL=99)) == 1.5

    from_settings = audit_cleanup.AuditLogCleanupWorker()
    assert from_settings._resolve_interval(SimpleNamespace(AUTHZ_AUDIT_CLEANUP_INTERVAL=99)) == 99.0


# --------------------------------------------------------------------------- #
# End-to-end: real retention helper deletes real rows on the schedule
# --------------------------------------------------------------------------- #


@pytest.fixture(name="audit_engine")
async def audit_engine():
    """A shared in-memory SQLite engine (StaticPool so every session sees the same DB)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


def _scope_factory(engine):
    @contextlib.asynccontextmanager
    async def _scope():
        # Mirror the real session_scope: commit on clean exit, roll back on error.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _scope


async def _count(engine, resource_id) -> int:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        rows = (await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.resource_id == resource_id))).all()
    return len(rows)


@pytest.mark.asyncio
async def test_worker_prunes_old_rows_on_schedule(audit_engine, monkeypatch):
    """A row inserted after startup is pruned by the scheduled worker; fresh rows survive."""
    old_id = uuid4()
    fresh_id = uuid4()
    async with AsyncSession(audit_engine, expire_on_commit=False) as session:
        session.add(_audit_row(days_old=120, resource_id=old_id))  # outside 90-day window
        session.add(_audit_row(days_old=2, resource_id=fresh_id))  # inside window
        await session.commit()

    monkeypatch.setattr(audit_cleanup, "session_scope", _scope_factory(audit_engine))
    monkeypatch.setattr(audit_cleanup, "get_settings_service", lambda: _svc(enabled=True, retention=90))

    from langflow.services.utils import clean_authz_audit_log as host_clean
    from langflow_services.providers import register_hook

    register_hook("clean_authz_audit_log", host_clean)

    worker = audit_cleanup.AuditLogCleanupWorker(interval=0.05)
    await worker.start()
    old_remaining = 1
    try:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + 5.0
        while loop.time() < deadline:
            await asyncio.sleep(0.1)
            old_remaining = await _count(audit_engine, old_id)
            if old_remaining == 0:
                break
    finally:
        await worker.stop()

    # The stale row was deleted by the recurring worker (the seed happened after
    # any startup sweep would have run), and the fresh row was left intact.
    assert old_remaining == 0
    assert await _count(audit_engine, fresh_id) == 1

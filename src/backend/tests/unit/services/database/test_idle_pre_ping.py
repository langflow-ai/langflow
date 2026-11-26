"""Tests for idle-gated pool pre-ping on DatabaseService engines."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from langflow.services.database.service import DatabaseService, _configure_idle_pre_ping
from lfx.services.settings.base import Settings
from sqlalchemy import Engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool


class _FakeClock:
    def __init__(self, initial: float = 100.0) -> None:
        self.now = initial

    def __call__(self) -> float:
        return self.now


def _make_database_service(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
    *,
    pool_pre_ping_idle_seconds: float = 0.0,
    db_connection_settings: dict | None = None,
) -> DatabaseService:
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", database_url)
    monkeypatch.setenv("LANGFLOW_POOL_PRE_PING_IDLE_SECONDS", str(pool_pre_ping_idle_seconds))
    if db_connection_settings is not None:
        monkeypatch.setenv("LANGFLOW_DB_CONNECTION_SETTINGS", json.dumps(db_connection_settings))
    else:
        monkeypatch.delenv("LANGFLOW_DB_CONNECTION_SETTINGS", raising=False)
    settings = Settings(_env_file=None)
    return DatabaseService(SimpleNamespace(settings=settings))


async def _dispose_database_service(db_service: DatabaseService) -> None:
    if event.contains(Engine, "connect", db_service.on_connection):
        event.remove(Engine, "connect", db_service.on_connection)
    await db_service.engine.dispose()
    if db_service._heartbeat_engine is not None:
        await db_service._heartbeat_engine.dispose()


@pytest.mark.asyncio
async def test_idle_pre_ping_skips_fresh_and_recent_checkouts_and_probes_after_idle(tmp_path):
    db_file = tmp_path / "idle_probe.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", pool_pre_ping=False)
    clock = _FakeClock()
    ping_results = [True]

    try:
        with (
            patch("langflow.services.database.service.time.monotonic", side_effect=clock),
            patch.object(
                engine.sync_engine.dialect,
                "do_ping",
                side_effect=lambda _conn: ping_results.pop(0),
            ) as mock_ping,
        ):
            _configure_idle_pre_ping(engine, idle_seconds=10.0)

            # 1. First checkout (fresh connection): no ping
            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
            assert mock_ping.call_count == 0

            # 2. Immediate re-checkout (idle 2s < 10s): no ping
            clock.now += 2.0
            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
            assert mock_ping.call_count == 0

            # 3. Re-checkout after >= 10s idle: probes via do_ping
            clock.now += 10.0
            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
            assert mock_ping.call_count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_idle_pre_ping_invalidates_stale_connection_on_failed_probe(tmp_path):
    db_file = tmp_path / "idle_stale.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", pool_pre_ping=False)
    clock = _FakeClock()
    ping_calls: list[bool] = []

    def _fake_ping(_conn) -> bool:
        result = len(ping_calls) > 0
        ping_calls.append(result)
        return result

    try:
        with (
            patch("langflow.services.database.service.time.monotonic", side_effect=clock),
            patch.object(engine.sync_engine.dialect, "do_ping", side_effect=_fake_ping),
        ):
            _configure_idle_pre_ping(engine, idle_seconds=5.0)

            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
            assert ping_calls == []

            clock.now += 6.0
            async with engine.connect() as conn:
                res = await conn.execute(sa.text("SELECT 1"))
                assert res.scalar_one() == 1
            assert ping_calls == [False]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_idle_pre_ping_invalidates_sibling_connections_in_pool(tmp_path):
    """A failed probe raises InvalidatePoolError so stale sibling connections are also recycled."""
    db_file = tmp_path / "idle_siblings.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=False,
    )
    clock = _FakeClock()
    fail_once = [True]

    def _fake_ping(_conn) -> bool:
        if fail_once[0]:
            fail_once[0] = False
            return False
        return True

    try:
        with (
            patch("langflow.services.database.service.time.monotonic", side_effect=clock),
            patch.object(engine.sync_engine.dialect, "do_ping", side_effect=_fake_ping),
        ):
            _configure_idle_pre_ping(engine, idle_seconds=5.0)

            # Populate two physical connections in the pool and record their DBAPI wrappers.
            async with engine.connect() as conn1, engine.connect() as conn2:
                await conn1.execute(sa.text("SELECT 1"))
                await conn2.execute(sa.text("SELECT 1"))
                old_ids = {
                    id((await conn1.get_raw_connection()).driver_connection),
                    id((await conn2.get_raw_connection()).driver_connection),
                }
            assert len(old_ids) == 2

            # Advance past idle window so the first checkout probes and fails.
            clock.now += 6.0
            async with engine.connect() as conn1, engine.connect() as conn2:
                await conn1.execute(sa.text("SELECT 1"))
                await conn2.execute(sa.text("SELECT 1"))
                new_ids = {
                    id((await conn1.get_raw_connection()).driver_connection),
                    id((await conn2.get_raw_connection()).driver_connection),
                }
            # Both the probed connection and its pooled sibling must be freshly created.
            assert old_ids.isdisjoint(new_ids)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_idle_pre_ping_reconnects_on_disconnect_exception_and_propagates_other_errors(tmp_path):
    db_file = tmp_path / "idle_exc.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", pool_pre_ping=False)
    clock = _FakeClock()
    disconnect_err = RuntimeError("server closed the connection unexpectedly")
    other_err = ValueError("unexpected driver error")
    calls = 0

    def _raise_disconnect(_conn) -> bool:
        nonlocal calls
        calls += 1
        raise disconnect_err

    try:
        with (
            patch("langflow.services.database.service.time.monotonic", side_effect=clock),
            patch.object(engine.sync_engine.dialect, "do_ping", side_effect=_raise_disconnect),
            patch.object(
                engine.sync_engine.dialect,
                "is_disconnect",
                side_effect=lambda err, _conn, _cur: err is disconnect_err,
            ),
        ):
            _configure_idle_pre_ping(engine, idle_seconds=5.0)

            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))

            clock.now += 6.0
            async with engine.connect() as conn:
                res = await conn.execute(sa.text("SELECT 1"))
                assert res.scalar_one() == 1
            assert calls == 1

        with (
            patch("langflow.services.database.service.time.monotonic", side_effect=clock),
            patch.object(engine.sync_engine.dialect, "do_ping", side_effect=other_err),
            patch.object(engine.sync_engine.dialect, "is_disconnect", return_value=False),
        ):
            clock.now += 6.0
            with pytest.raises(ValueError, match="unexpected driver error"):
                async with engine.connect():
                    pass
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_database_service_create_engine_wiring_for_sqlite_and_default_zero(monkeypatch, tmp_path):
    """SQLite and default pool_pre_ping_idle_seconds=0 keep native SQLAlchemy pool_pre_ping."""
    created_calls: list[tuple[str, dict]] = []

    def _fake_create_async_engine(url: str, **kwargs):
        created_calls.append((url, dict(kwargs)))
        return create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'stub.db'}", pool_pre_ping=kwargs.get("pool_pre_ping", False)
        )

    with (
        patch("langflow.services.database.service.create_async_engine", side_effect=_fake_create_async_engine),
        patch("langflow.services.database.service._configure_idle_pre_ping") as mock_configure,
    ):
        sqlite_service = _make_database_service(
            monkeypatch,
            f"sqlite:///{tmp_path / 'wiring.db'}",
            pool_pre_ping_idle_seconds=10.0,
        )
        pg_default_service = _make_database_service(
            monkeypatch,
            "postgresql://user:pass@localhost:5432/langflow",
            pool_pre_ping_idle_seconds=0.0,
        )
        try:
            assert created_calls[0][0].startswith("sqlite+aiosqlite://")
            assert created_calls[0][1]["pool_pre_ping"] is True
            assert created_calls[1][0].startswith("postgresql+psycopg://")
            assert created_calls[1][1]["pool_pre_ping"] is True
            mock_configure.assert_not_called()
        finally:
            await _dispose_database_service(sqlite_service)
            await _dispose_database_service(pg_default_service)


@pytest.mark.asyncio
async def test_database_service_create_engine_wiring_for_non_sqlite_opt_in(monkeypatch, tmp_path):
    """Non-SQLite with pool_pre_ping_idle_seconds > 0 disables native pre_ping and attaches idle probe."""
    created_calls: list[tuple[str, dict]] = []

    def _fake_create_async_engine(url: str, **kwargs):
        created_calls.append((url, dict(kwargs)))
        return create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'stub.db'}", pool_pre_ping=kwargs.get("pool_pre_ping", False)
        )

    with (
        patch("langflow.services.database.service.create_async_engine", side_effect=_fake_create_async_engine),
        patch("langflow.services.database.service._configure_idle_pre_ping") as mock_configure,
    ):
        pg_service = _make_database_service(
            monkeypatch,
            "postgresql://user:pass@localhost:5432/langflow",
            pool_pre_ping_idle_seconds=10.0,
        )
        heartbeat_engine = pg_service._create_heartbeat_engine()
        pg_service._heartbeat_engine = heartbeat_engine
        try:
            # Main app pool disables native pool_pre_ping and registers the idle probe.
            assert created_calls[0][0].startswith("postgresql+psycopg://")
            assert created_calls[0][1]["pool_pre_ping"] is False
            mock_configure.assert_called_once_with(pg_service.engine, 10.0)
            # Dedicated heartbeat engine keeps unconditional pool_pre_ping=True.
            assert created_calls[1][0].startswith("postgresql+psycopg://")
            assert created_calls[1][1]["pool_pre_ping"] is True
        finally:
            await _dispose_database_service(pg_service)


@pytest.mark.asyncio
async def test_database_service_create_engine_respects_pool_pre_ping_false(monkeypatch, tmp_path):
    """Explicit pool_pre_ping=False disables both native and idle-gated probing."""
    created_calls: list[tuple[str, dict]] = []

    def _fake_create_async_engine(url: str, **kwargs):
        created_calls.append((url, dict(kwargs)))
        return create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'stub.db'}", pool_pre_ping=kwargs.get("pool_pre_ping", False)
        )

    with (
        patch("langflow.services.database.service.create_async_engine", side_effect=_fake_create_async_engine),
        patch("langflow.services.database.service._configure_idle_pre_ping") as mock_configure,
    ):
        pg_service = _make_database_service(
            monkeypatch,
            "postgresql://user:pass@localhost:5432/langflow",
            pool_pre_ping_idle_seconds=10.0,
            db_connection_settings={"pool_size": 5, "max_overflow": 5, "pool_pre_ping": False},
        )
        try:
            assert created_calls[0][0].startswith("postgresql+psycopg://")
            assert created_calls[0][1]["pool_pre_ping"] is False
            mock_configure.assert_not_called()
        finally:
            await _dispose_database_service(pg_service)


@pytest.mark.skipif(
    not os.environ.get("LANGFLOW_TEST_POSTGRES_URL"),
    reason="set LANGFLOW_TEST_POSTGRES_URL",
)
def test_idle_pre_ping_postgres_end_to_end(monkeypatch):
    """Exercise DatabaseService._create_engine against live PostgreSQL with do_ping unpatched."""

    async def _run() -> None:
        pg_url = os.environ["LANGFLOW_TEST_POSTGRES_URL"]
        clock = _FakeClock()

        admin_url = pg_url
        if admin_url.startswith("postgresql://"):
            admin_url = admin_url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif admin_url.startswith("postgres://"):
            admin_url = admin_url.replace("postgres://", "postgresql+psycopg://", 1)
        admin_engine = create_async_engine(admin_url, pool_pre_ping=True)

        with patch("langflow.services.database.service.time.monotonic", side_effect=clock):
            db_service = _make_database_service(
                monkeypatch,
                pg_url,
                pool_pre_ping_idle_seconds=10.0,
                db_connection_settings={
                    "pool_size": 2,
                    "max_overflow": 0,
                    "pool_timeout": 10,
                    "pool_pre_ping": True,
                    "pool_recycle": 1800,
                    "echo": False,
                },
            )
            try:
                assert db_service.engine.sync_engine.pool._pre_ping is False

                # 1. Open two concurrent connections so both live in the pool, then release them.
                async with db_service.engine.connect() as c1, db_service.engine.connect() as c2:
                    pid1 = (await c1.execute(sa.text("SELECT pg_backend_pid()"))).scalar_one()
                    pid2 = (await c2.execute(sa.text("SELECT pg_backend_pid()"))).scalar_one()
                assert pid1 != pid2

                # 2. Terminate both backends (simulating DB restart/failover), advance past idle window.
                async with admin_engine.connect() as admin:
                    await admin.execute(sa.text("SELECT pg_terminate_backend(:pid)"), {"pid": pid1})
                    await admin.execute(sa.text("SELECT pg_terminate_backend(:pid)"), {"pid": pid2})

                clock.now += 11.0

                # First checkout probes via real psycopg do_ping, detects the terminated backend,
                # raises InvalidatePoolError (invalidating sibling pid2 too), and reconnects cleanly.
                async with db_service.engine.connect() as c1, db_service.engine.connect() as c2:
                    new_pid1 = (await c1.execute(sa.text("SELECT pg_backend_pid()"))).scalar_one()
                    new_pid2 = (await c2.execute(sa.text("SELECT pg_backend_pid()"))).scalar_one()
                assert {new_pid1, new_pid2}.isdisjoint({pid1, pid2})

                # 3. Terminate connections inside the idle window: pre-ping is skipped, so the query
                # itself observes the disconnect (proving no probe ran inside the idle window).
                async with admin_engine.connect() as admin:
                    await admin.execute(sa.text("SELECT pg_terminate_backend(:pid)"), {"pid": new_pid1})
                    await admin.execute(sa.text("SELECT pg_terminate_backend(:pid)"), {"pid": new_pid2})

                clock.now += 2.0
                with pytest.raises(OperationalError):
                    async with db_service.engine.connect() as conn:
                        await conn.execute(sa.text("SELECT 1"))
            finally:
                await _dispose_database_service(db_service)
                await admin_engine.dispose()

    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(_run(), loop_factory=loop_factory)

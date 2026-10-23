"""Database sessions opened from a second event loop use connections owned by that loop.

``run_until_complete`` runs a coroutine on a new loop in a worker thread when the
caller is already on a loop, and ``asyncio.to_thread`` callers start their own
loop with ``asyncio.run``. SQLAlchemy's async queue pool waits on an
``asyncio.Queue`` bound to one loop, and a pooled driver connection belongs to
the loop that opened it. These tests drive a real ``DatabaseService`` with a
one-connection pool from such loops while the application loop holds that
connection.

Set LANGFLOW_TEST_POSTGRES_URL (or LANGFLOW_TEST_DATABASE_URI, as CI does) to
also run against PostgreSQL.
"""

from __future__ import annotations

import asyncio
import contextvars
import os
import threading
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from langflow.services.database.service import DatabaseService
from lfx.utils.async_helpers import run_until_complete
from sqlalchemy import event, text
from sqlalchemy.pool import Pool

_TENANT: contextvars.ContextVar[str] = contextvars.ContextVar("cross_loop_test_tenant", default="unset")


def _postgres_url() -> str | None:
    return os.environ.get("LANGFLOW_TEST_POSTGRES_URL") or os.environ.get("LANGFLOW_TEST_DATABASE_URI")


def _make_service(database_url: str, connection_settings: dict | None = None) -> DatabaseService:
    settings_service = MagicMock()
    settings = settings_service.settings
    settings.database_url = database_url
    settings.database_connection_retry = False
    settings.use_noop_database = False
    settings.sqlite_pragmas = {}
    settings.db_driver_connection_settings = None
    settings.db_connection_settings = (
        {"pool_size": 1, "max_overflow": 0, "pool_timeout": 5} if connection_settings is None else connection_settings
    )
    settings.alembic_log_to_stdout = True
    return DatabaseService(settings_service)


@pytest.fixture(params=["sqlite", "postgresql"])
async def db_service(request, tmp_path):
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path / 'cross_loop.db'}"
    else:
        url = _postgres_url()
        if not url:
            pytest.skip("LANGFLOW_TEST_POSTGRES_URL or LANGFLOW_TEST_DATABASE_URI is not set")
    service = _make_service(url)
    try:
        yield service
    finally:
        await service.engine.dispose()


async def _select(service: DatabaseService, value: int = 1) -> int:
    async with service._with_session() as session:
        return (await session.exec(text(f"SELECT {int(value)}"))).one()[0]


async def _bind_pool_wait_queue_to_running_loop(service: DatabaseService) -> None:
    """Make the application loop wait for a connection once, as it does under load."""
    async with service._with_session() as holder:
        await holder.exec(text("SELECT 1"))
        waiter = asyncio.create_task(_select(service))
        await asyncio.sleep(0.05)
        assert not waiter.done()
    assert await asyncio.wait_for(waiter, 5) == 1


@contextmanager
def _track_connections():
    """Record the identity of every DBAPI connection any pool opens and closes."""
    opened: set[int] = set()
    closed: set[int] = set()

    def on_connect(dbapi_connection, _record):
        opened.add(id(dbapi_connection))

    def on_close(dbapi_connection, _record):
        closed.add(id(dbapi_connection))

    event.listen(Pool, "connect", on_connect)
    event.listen(Pool, "close", on_close)
    try:
        yield opened, closed
    finally:
        event.remove(Pool, "connect", on_connect)
        event.remove(Pool, "close", on_close)


async def test_bridged_session_does_not_wait_on_the_application_loop_pool(db_service):
    await _bind_pool_wait_queue_to_running_loop(db_service)

    with _track_connections() as (opened, closed):
        async with db_service._with_session() as holder:
            await holder.exec(text("SELECT 1"))
            # The bridge blocks this loop, so the held connection cannot return
            # to the pool until the bridged coroutine finishes.
            assert run_until_complete(asyncio.wait_for(_select(db_service, 7), 5)) == 7

    assert db_service.engine.pool.checkedout() == 0
    # The application loop's connection was opened before tracking started, so
    # every tracked connection belongs to the bridge's loop, which has closed.
    assert opened, "the bridged coroutine should open its own connection"
    assert closed == opened


async def test_to_thread_session_does_not_wait_on_the_application_loop_pool(db_service):
    await _bind_pool_wait_queue_to_running_loop(db_service)

    async with db_service._with_session() as holder:
        await holder.exec(text("SELECT 1"))
        result = await asyncio.wait_for(
            asyncio.to_thread(run_until_complete, _select(db_service, 3)),
            10,
        )

    assert result == 3
    assert await _select(db_service, 4) == 4


async def test_concurrent_worker_loops_keep_their_own_context(db_service):
    async def read_as(tenant: str) -> tuple[str, int]:
        value = await _select(db_service, len(tenant))
        await asyncio.sleep(0.01)
        return _TENANT.get(), value

    def bridged(tenant: str) -> tuple[str, int]:
        _TENANT.set(tenant)
        return run_until_complete(read_as(tenant))

    async with db_service._with_session() as holder:
        await holder.exec(text("SELECT 1"))
        tenants = [f"tenant-{'x' * i}" for i in range(6)]
        results = await asyncio.wait_for(
            asyncio.gather(*(asyncio.to_thread(bridged, tenant) for tenant in tenants)),
            15,
        )

    assert results == [(tenant, len(tenant)) for tenant in tenants]


def test_sequential_main_thread_loops_close_their_connections(tmp_path):
    service = _make_service(f"sqlite:///{tmp_path / 'sequential.db'}")
    with _track_connections() as (opened, closed):
        for value in (1, 2, 3):
            assert asyncio.run(_select(service, value)) == value

    # Each loop closes the connections it opened when it shuts down.
    assert len(opened) == 3
    assert closed == opened
    assert service.engine.pool.checkedout() == 0


def test_main_thread_loop_after_a_stopped_loop_gets_a_new_pool(tmp_path):
    service = _make_service(f"sqlite:///{tmp_path / 'stopped.db'}")
    stopped = asyncio.new_event_loop()
    try:
        # This loop waits on the pool, then stops without shutting down.
        stopped.run_until_complete(_bind_pool_wait_queue_to_running_loop(service))
        asyncio.run(_bind_pool_wait_queue_to_running_loop(service))
        assert asyncio.run(_select(service, 5)) == 5
    finally:
        stopped.close()


def test_worker_thread_loop_engine_is_released_when_the_loop_closes(tmp_path):
    service = _make_service(f"sqlite:///{tmp_path / 'worker.db'}")
    result: list[int] = []
    with _track_connections() as (opened, closed):
        assert asyncio.run(_select(service, 1)) == 1
        worker = threading.Thread(target=lambda: result.append(asyncio.run(_select(service, 2))))
        worker.start()
        worker.join(10)

    assert result == [2]
    assert len(opened) == 2
    assert closed == opened
    assert service._loop_engines == {}


async def test_in_memory_sqlite_bridged_session_reads_the_same_database():
    # StaticPool keeps one in-memory database on one connection; a second engine
    # would see an empty database, so every loop shares it.
    service = _make_service("sqlite://", {"poolclass": "StaticPool"})
    try:
        async with service._with_session() as session:
            await session.exec(text("CREATE TABLE marker (value INTEGER)"))
            await session.exec(text("INSERT INTO marker VALUES (11)"))
            await session.commit()

        async def read_marker() -> int:
            async with service._with_session() as session:
                return (await session.exec(text("SELECT value FROM marker"))).one()[0]

        assert await asyncio.to_thread(run_until_complete, read_marker()) == 11
    finally:
        await service.engine.dispose()

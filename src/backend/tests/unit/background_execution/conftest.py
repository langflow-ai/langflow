"""Real-instance fixtures for the background-execution hard-proof tier.

These fixtures back ``@pytest.mark.hard_proof`` tests with REAL engines, never
fakes:

- ``hard_proof_db_url`` parametrizes over real SQLite (always) and real Postgres
  (only when ``LANGFLOW_TEST_DATABASE_URI`` is set; CI always sets it).
- ``hard_proof_redis_url`` yields a real Redis URL from ``LANGFLOW_TEST_REDIS_URL``
  (skips when unset), flushed clean before and after each test.
- ``hard_proof_job_service`` runs the real Alembic migrations against
  ``hard_proof_db_url`` and binds ``session_scope()`` to it, so store methods are
  exercised on both real SQLite and real Postgres.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from langflow.services.jobs.service import JobService


def _async_pg_url(raw: str) -> str:
    """Normalize a Postgres URL to the async asyncpg dialect (the driver we install)."""
    if "+asyncpg" in raw or "+psycopg" in raw:
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw


@pytest.fixture(params=["sqlite", "postgres"])
async def hard_proof_db_url(request: pytest.FixtureRequest) -> AsyncGenerator[str, None]:
    """Yield a real, connectable async DB URL.

    - sqlite: a real temp-file SQLite database (always runs).
    - postgres: the database behind ``LANGFLOW_TEST_DATABASE_URI`` normalized to
      the asyncpg dialect; skipped when the env var is unset (CI always sets it).
    """
    if request.param == "sqlite":
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        try:
            yield f"sqlite+aiosqlite:///{db_path}"
        finally:
            for suffix in ("", "-wal", "-shm", "-journal"):
                Path(db_path + suffix).unlink(missing_ok=True)
    else:
        raw = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
        if not raw:
            pytest.skip("LANGFLOW_TEST_DATABASE_URI not set")
        yield _async_pg_url(raw)


@pytest.fixture
async def hard_proof_job_service(hard_proof_db_url: str) -> AsyncGenerator[JobService, None]:
    """Yield a JobService whose ``session_scope()`` is bound to a real, migrated DB.

    Runs the real Alembic migrations against ``hard_proof_db_url`` (sqlite + postgres)
    through the production ``DatabaseService`` path, then swaps that service into the
    service manager so ``JobService``'s ``session_scope()`` resolves to it. This proves
    the store methods on BOTH real SQLite and real Postgres, and that the migrations
    themselves apply on both engines.
    """
    from langflow.services.database.factory import DatabaseServiceFactory
    from langflow.services.deps import get_settings_service
    from langflow.services.jobs.service import JobService
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    manager = get_service_manager()
    settings_service = get_settings_service()
    original_url = settings_service.settings.database_url
    original_db_service = manager.services.pop(ServiceType.DATABASE_SERVICE, None)

    settings_service.settings.database_url = hard_proof_db_url
    db_service = DatabaseServiceFactory().create(settings_service)
    manager.services[ServiceType.DATABASE_SERVICE] = db_service

    try:
        await db_service.run_migrations()
        yield JobService()
    finally:
        manager.services.pop(ServiceType.DATABASE_SERVICE, None)
        with contextlib.suppress(Exception):
            await db_service.teardown()
        settings_service.settings.database_url = original_url
        if original_db_service is not None:
            manager.services[ServiceType.DATABASE_SERVICE] = original_db_service


@pytest.fixture
async def hard_proof_redis_url() -> AsyncGenerator[str, None]:
    """Yield a real Redis URL from ``LANGFLOW_TEST_REDIS_URL``, flushed clean.

    Skips when ``LANGFLOW_TEST_REDIS_URL`` is unset (CI sets it via the redis:7
    service). Uses the same ``redis.asyncio`` client ``RedisJobQueueService`` uses,
    so this exercises the real driver, not fakeredis.
    """
    url = os.environ.get("LANGFLOW_TEST_REDIS_URL")
    if not url:
        pytest.skip("LANGFLOW_TEST_REDIS_URL not set")

    from redis.asyncio import StrictRedis

    client = StrictRedis.from_url(url)
    try:
        await client.flushdb()
        yield url
    finally:
        with contextlib.suppress(Exception):
            await client.flushdb()
        await client.aclose()

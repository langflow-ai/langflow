"""API-key usage bookkeeping must survive overlapping authentications (#16304).

The SQLite case always runs. Set LANGFLOW_TEST_POSTGRES_URL (or
LANGFLOW_TEST_DATABASE_URI, as CI does) to a PostgreSQL URL whose user can
create schemas to also run the PostgreSQL case; it owns a temporary schema.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import anyio
import pytest
from langflow.services.database.models.api_key.crud import (
    _authenticate_api_key_in_owned_scope,
    _check_key_from_db_with_context,
    hash_api_key,
)
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.maintenance import MaintenanceState
from langflow.services.database.models.user.model import User
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

CONCURRENT_REQUESTS = 4
INITIAL_USES = 7


def _postgres_url() -> str | None:
    url = os.environ.get("LANGFLOW_TEST_POSTGRES_URL") or os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not url or "+psycopg" in url:
        return url
    return url.replace("postgresql://", "postgresql+psycopg://", 1).replace("postgres://", "postgresql+psycopg://", 1)


def _settings(*, disable_tracking: bool) -> SimpleNamespace:
    return SimpleNamespace(
        auth_settings=SimpleNamespace(API_KEY_SOURCE="db", EXTERNAL_AUTH_ACCESS_CEILING_ENABLED=False),
        settings=SimpleNamespace(disable_track_apikey_usage=disable_tracking),
    )


def _as_utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes; every write uses UTC.
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


@pytest.fixture(params=["sqlite", "postgresql"])
async def usage_engine(request, tmp_path):
    admin = None
    schema = f"api_key_usage_{uuid4().hex}"
    if request.param == "sqlite":
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'usage.db'}")
    else:
        url = _postgres_url()
        if not url:
            pytest.skip("LANGFLOW_TEST_POSTGRES_URL or LANGFLOW_TEST_DATABASE_URI is not set")
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(CreateSchema(schema))
        engine = create_async_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda conn: SQLModel.metadata.create_all(
                    conn, tables=[User.__table__, ApiKey.__table__, MaintenanceState.__table__]
                )
            )
        yield engine
    finally:
        try:
            await engine.dispose()
        finally:
            if admin is not None:
                try:
                    async with admin.begin() as connection:
                        await connection.execute(DropSchema(schema, cascade=True))
                finally:
                    await admin.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("hashed", [True, False], ids=["hashed", "legacy"])
@pytest.mark.parametrize("disable_tracking", [False, True], ids=["tracking", "no-tracking"])
async def test_overlapping_authentications_count_every_use(usage_engine, monkeypatch, *, hashed, disable_tracking):
    """Transactions that all read the same counter must still persist one use each."""
    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.get_settings_service",
        lambda: _settings(disable_tracking=disable_tracking),
    )
    plaintext = f"sk-concurrent-{uuid4().hex}"  # pragma: allowlist secret
    user = User(username=f"concurrent-{uuid4().hex}", password="unused", is_active=True)  # noqa: S106
    key = ApiKey(
        api_key=plaintext,
        api_key_hash=hash_api_key(plaintext) if hashed else None,
        name="concurrency",
        user_id=user.id,
        total_uses=INITIAL_USES,
    )
    key_id = key.id
    async with AsyncSession(usage_engine, expire_on_commit=False) as session, session.begin():
        session.add(user)
        session.add(key)

    updates: list[str] = []

    @event.listens_for(usage_engine.sync_engine, "before_cursor_execute")
    def record_updates(_conn, _cursor, statement, _params, _context, _executemany):
        if statement.lstrip().upper().startswith("UPDATE APIKEY "):
            updates.append(statement)

    # Hold every request after it has loaded the key row and its owner, so all of
    # them read the same total_uses before any of them writes.
    all_read = anyio.Event()
    readers = 0

    class ReadBarrierSession(AsyncSession):
        async def get(self, entity, ident, **kwargs):
            nonlocal readers
            result = await super().get(entity, ident, **kwargs)
            if entity is User:
                readers += 1
                if readers == CONCURRENT_REQUESTS:
                    all_read.set()
                await all_read.wait()
            return result

    @asynccontextmanager
    async def auth_scope():
        async with ReadBarrierSession(usage_engine, expire_on_commit=False) as session, session.begin():
            yield session

    async def authenticate():
        result = await _authenticate_api_key_in_owned_scope(plaintext, auth_scope)
        assert result is not None
        assert result.user.id == user.id
        assert result.api_key_id == key_id

    with anyio.fail_after(15):
        async with anyio.create_task_group() as tasks:
            for _ in range(CONCURRENT_REQUESTS):
                tasks.start_soon(authenticate)

    # Without this the barrier could silently stop forcing the overlap.
    assert readers == CONCURRENT_REQUESTS

    async with AsyncSession(usage_engine) as session:
        persisted = await session.get(ApiKey, key_id)
    assert persisted is not None
    assert persisted.total_uses == INITIAL_USES + (0 if disable_tracking else CONCURRENT_REQUESTS)
    assert (persisted.last_used_at is None) is disable_tracking
    # The legacy hash backfill is independent of usage tracking.
    assert persisted.api_key_hash == hash_api_key(plaintext)
    # One UPDATE per authentication that has something to write; none for a
    # hashed key with tracking disabled.
    expected_updates = 0 if (hashed and disable_tracking) else CONCURRENT_REQUESTS
    assert len(updates) == expected_updates


async def _seed_key(async_session, *, hashed: bool, last_used_at: datetime) -> tuple[str, ApiKey]:
    plaintext = f"sk-timestamp-{uuid4().hex}"  # pragma: allowlist secret
    user = User(username=f"timestamp-{uuid4().hex}", password="unused", is_active=True)  # noqa: S106
    key = ApiKey(
        api_key=plaintext,
        api_key_hash=hash_api_key(plaintext) if hashed else None,
        name="timestamp",
        user_id=user.id,
        last_used_at=last_used_at,
    )
    async_session.add(user)
    async_session.add(key)
    await async_session.commit()
    return plaintext, key


@pytest.mark.anyio
@pytest.mark.parametrize("hashed", [True, False], ids=["hashed", "legacy"])
async def test_authentication_moves_last_used_at_forward(async_session, *, hashed):
    """An older stored timestamp is replaced by the time of the new authentication."""
    plaintext, key = await _seed_key(
        async_session, hashed=hashed, last_used_at=datetime(2000, 1, 1, tzinfo=timezone.utc)
    )

    before = datetime.now(timezone.utc)
    assert await _check_key_from_db_with_context(async_session, plaintext, _settings(disable_tracking=False))
    await async_session.commit()
    await async_session.refresh(key)

    assert key.total_uses == 1
    assert _as_utc(key.last_used_at) >= before


@pytest.mark.anyio
@pytest.mark.parametrize("hashed", [True, False], ids=["hashed", "legacy"])
async def test_authentication_never_moves_last_used_at_backwards(async_session, *, hashed):
    """A request that samples an earlier time must not overwrite a newer stored timestamp."""
    newer = datetime(2099, 1, 1, tzinfo=timezone.utc)
    plaintext, key = await _seed_key(async_session, hashed=hashed, last_used_at=newer)

    assert await _check_key_from_db_with_context(async_session, plaintext, _settings(disable_tracking=False))
    await async_session.commit()
    await async_session.refresh(key)

    assert key.total_uses == 1
    assert _as_utc(key.last_used_at) == newer

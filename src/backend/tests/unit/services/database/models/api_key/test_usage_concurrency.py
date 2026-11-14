"""Authentication bookkeeping must survive overlapping reads (#16304)."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from os import getenv
from types import SimpleNamespace
from uuid import uuid4

import anyio
import pytest
from langflow.services.database.models.api_key.crud import _authenticate_api_key_in_owned_scope, hash_api_key
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.maintenance import MaintenanceState
from langflow.services.database.models.user.model import User
from sqlalchemy import delete, event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.mark.anyio
@pytest.mark.parametrize("hashed", [True, False])
@pytest.mark.parametrize("disable_tracking", [True, False])
async def test_overlapping_authentication_preserves_every_use(tmp_path, monkeypatch, *, hashed, disable_tracking):
    """Independent auth transactions may read the same counter, but each successful use persists."""
    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(API_KEY_SOURCE="db", EXTERNAL_AUTH_ACCESS_CEILING_ENABLED=False),
        settings=SimpleNamespace(disable_track_apikey_usage=disable_tracking),
    )
    monkeypatch.setattr("langflow.services.database.models.api_key.crud.get_settings_service", lambda: settings)
    database_url = getenv("LANGFLOW_TEST_API_KEY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'usage.db'}")
    engine = create_async_engine(database_url)
    plaintext = f"sk-concurrent-{uuid4().hex}"  # pragma: allowlist secret
    user = User(username=f"concurrent-{uuid4().hex}", password="unused", is_active=True)  # noqa: S106
    key = ApiKey(
        api_key=plaintext,
        api_key_hash=hash_api_key(plaintext) if hashed else None,
        name="concurrency",
        user_id=user.id,
        total_uses=7,
    )
    key_id = key.id
    ready = anyio.Event()
    readers = 0
    requests = 4
    rows_created = False
    updates = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def observe_updates(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("UPDATE APIKEY "):
            updates.append(statement)

    class ReadBarrierSession(AsyncSession):
        async def get(self, entity, ident, **kwargs):
            nonlocal readers
            result = await super().get(entity, ident, **kwargs)
            if entity is User:
                readers += 1
                if readers == requests:
                    ready.set()
                await ready.wait()
            return result

    @asynccontextmanager
    async def auth_scope():
        async with ReadBarrierSession(engine, expire_on_commit=False) as session, session.begin():
            yield session

    async def authenticate():
        result = await _authenticate_api_key_in_owned_scope(plaintext, auth_scope)
        assert result is not None
        assert result.user.id == user.id
        assert result.api_key_id == key_id

    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda conn: SQLModel.metadata.create_all(
                    conn, tables=[User.__table__, ApiKey.__table__, MaintenanceState.__table__]
                )
            )
        async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
            session.add(user)
            session.add(key)
        rows_created = True
        with anyio.fail_after(15):
            async with anyio.create_task_group() as tasks:
                for _ in range(requests):
                    tasks.start_soon(authenticate)
        async with AsyncSession(engine) as session:
            persisted = await session.get(ApiKey, key_id)
            assert persisted is not None
            assert persisted.total_uses == 7 + (0 if disable_tracking else requests)
            assert persisted.api_key_hash == (hash_api_key(plaintext) if hashed or not disable_tracking else None)
            assert (persisted.last_used_at is None) is disable_tracking
        assert len(updates) == (0 if disable_tracking else requests)
    finally:
        try:
            if rows_created:
                async with AsyncSession(engine) as session, session.begin():
                    await session.execute(delete(ApiKey).where(ApiKey.id == key_id))
                    await session.execute(delete(User).where(User.id == user.id))
        finally:
            await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("hashed", [True, False])
async def test_authentication_does_not_move_last_used_at_backwards(async_session, *, hashed):
    """An earlier sampled request timestamp must not overwrite a newer persisted timestamp."""
    from langflow.services.database.models.api_key.crud import _check_key_from_db_with_context

    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(EXTERNAL_AUTH_ACCESS_CEILING_ENABLED=False),
        settings=SimpleNamespace(disable_track_apikey_usage=False),
    )
    plaintext = f"sk-monotonic-{uuid4().hex}"  # pragma: allowlist secret
    user = User(username=f"monotonic-{uuid4().hex}", password="unused", is_active=True)  # noqa: S106
    newer = datetime(2099, 1, 1, tzinfo=timezone.utc)
    key = ApiKey(
        api_key=plaintext, api_key_hash=hash_api_key(plaintext) if hashed else None, user_id=user.id, last_used_at=newer
    )
    async_session.add(user)
    async_session.add(key)
    await async_session.commit()

    assert await _check_key_from_db_with_context(async_session, plaintext, settings) is not None
    await async_session.commit()
    await async_session.refresh(key)
    assert key.last_used_at.replace(tzinfo=timezone.utc) == newer
    assert key.total_uses == 1

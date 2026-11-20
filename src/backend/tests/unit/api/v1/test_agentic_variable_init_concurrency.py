"""Concurrent agentic placeholder initialization on SQLite and PostgreSQL.

Set LANGFLOW_TEST_POSTGRES_URL (or LANGFLOW_TEST_DATABASE_URI, as CI does) to a
``postgresql+psycopg://`` URL (psycopg 3) for a test database whose user can create schemas. Each
PostgreSQL case owns a temporary schema.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from langflow.api.utils.mcp.agentic_mcp import (
    _STARTUP_AGENTIC_PLACEHOLDERS,
    _create_missing_agentic_variables,
    initialize_agentic_global_variables,
    initialize_agentic_user_variables,
)
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import GENERIC_TYPE
from sqlalchemy import func
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, InvalidRequestError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

GLOBAL_PLACEHOLDER_NAMES = ("COMPONENT_ID", "FIELD_NAME", "FLOW_ID")


def _postgres_url() -> str | None:
    url = os.environ.get("LANGFLOW_TEST_POSTGRES_URL") or os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not url:
        return None
    parsed = make_url(url)
    if parsed.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
        msg = "PostgreSQL concurrency tests require postgresql+psycopg:// (psycopg 3)"
        raise ValueError(msg)
    return parsed.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


@pytest.fixture(params=["sqlite", "postgresql", "postgresql-repeatable-read"])
async def placeholder_database(request, tmp_path):
    admin = None
    schema = f"agentic_init_{uuid4().hex}"
    if request.param == "sqlite":
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'agentic-init.db'}",
            connect_args={"timeout": 30},
        )
    else:
        url = _postgres_url()
        if not url:
            pytest.skip("LANGFLOW_TEST_POSTGRES_URL or LANGFLOW_TEST_DATABASE_URI is not set")
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(CreateSchema(schema))
        engine = create_async_engine(
            url,
            connect_args={"options": f"-csearch_path={schema}"},
            isolation_level="REPEATABLE READ" if request.param.endswith("repeatable-read") else "READ COMMITTED",
        )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        yield engine
    finally:
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
            await admin.dispose()


async def _seed_user(engine) -> User:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = User(id=uuid4(), username=f"agentic-{uuid4().hex[:8]}", password="x", is_active=True)  # noqa: S106
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _names(engine, user_id) -> list[str]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        rows = (await session.exec(select(Variable).where(Variable.user_id == user_id))).all()
        return [row.name for row in rows]


async def test_concurrent_workers_create_one_row_per_placeholder(placeholder_database, monkeypatch):
    user = await _seed_user(placeholder_database)
    first_ready = asyncio.Event()
    second_lock_attempt = asyncio.Event()
    service = get_variable_service()
    original_counts = service.existing_variable_name_counts
    observed_second_check = []

    class CoordinatedSession(AsyncSession):
        async def exec(self, statement, *args, **kwargs):
            locks_user = getattr(statement, "_for_update_arg", None) is not None
            reserves_writer = getattr(statement, "is_update", False)
            if self.info.get("second") and (locks_user or reserves_writer):
                assert first_ready.is_set()
                second_lock_attempt.set()
            return await super().exec(statement, *args, **kwargs)

    async def checked_counts(user_id, names, session):
        counts = await original_counts(user_id, names, session=session)
        if session.info.get("second"):
            # This query must see the first worker's committed rows, not an old snapshot.
            assert counts == dict.fromkeys(GLOBAL_PLACEHOLDER_NAMES, 1)
            if session.get_bind().dialect.name == "postgresql":
                assert await (await session.connection()).get_isolation_level() == "READ COMMITTED"
            observed_second_check.append(counts)
        return counts

    monkeypatch.setattr(service, "existing_variable_name_counts", checked_counts)

    async def first_worker():
        async with CoordinatedSession(placeholder_database, expire_on_commit=False) as session:
            await initialize_agentic_global_variables(session)
            first_ready.set()
            # Do not commit until the other worker reaches the real lock statement.
            await second_lock_attempt.wait()
            await session.commit()

    async def second_worker():
        await first_ready.wait()
        async with CoordinatedSession(placeholder_database, expire_on_commit=False) as session:
            session.info["second"] = True
            await initialize_agentic_global_variables(session)
            await session.commit()

    await asyncio.wait_for(asyncio.gather(first_worker(), second_worker()), timeout=20)
    assert len(observed_second_check) == 1
    assert sorted(await _names(placeholder_database, user.id)) == sorted(GLOBAL_PLACEHOLDER_NAMES)


async def test_integrity_error_savepoint_allows_remaining_creates(placeholder_database, monkeypatch):
    """An actual failed flush must roll back only its savepoint, not the session."""
    user = await _seed_user(placeholder_database)
    collision_id = uuid4()
    async with AsyncSession(placeholder_database) as session:
        session.add(Variable(id=collision_id, user_id=user.id, name="UNCHANGED", value="keep", type=GENERIC_TYPE))
        await session.commit()

    service = get_variable_service()
    original = service.create_variable
    calls = []

    async def failing_create(*args, **kwargs):
        calls.append(kwargs["name"])
        if len(calls) == 1:
            session = kwargs["session"]
            session.add(Variable(id=collision_id, user_id=user.id, name="FLOW_ID", value="failed", type=GENERIC_TYPE))
            await session.flush()  # A real primary-key violation poisons the transaction without a savepoint.
        return await original(*args, **kwargs)

    monkeypatch.setattr(service, "create_variable", failing_create)
    async with AsyncSession(placeholder_database, expire_on_commit=False) as session:
        created, skipped = await _create_missing_agentic_variables(
            session, user.id, _STARTUP_AGENTIC_PLACEHOLDERS, GENERIC_TYPE, user_label=user.username
        )
        assert (created, skipped) == (2, 0)  # The failed FLOW_ID was not a competing insert.
        assert session.is_active
        await session.commit()

    assert calls == ["FLOW_ID", "COMPONENT_ID", "FIELD_NAME"]
    assert sorted(await _names(placeholder_database, user.id)) == ["COMPONENT_ID", "FIELD_NAME", "UNCHANGED"]
    async with AsyncSession(placeholder_database) as session:
        unchanged = await session.get(Variable, collision_id)
        assert unchanged.name == "UNCHANGED"
        assert unchanged.value == "keep"


async def test_recoverable_sqlalchemy_error_attempts_later_names(placeholder_database, monkeypatch):
    user = await _seed_user(placeholder_database)
    service = get_variable_service()
    original = service.create_variable
    calls = []

    async def failing_create(*args, **kwargs):
        calls.append(kwargs["name"])
        if kwargs["name"] == "COMPONENT_ID":
            msg = "recoverable service failure"
            raise InvalidRequestError(msg)
        return await original(*args, **kwargs)

    monkeypatch.setattr(service, "create_variable", failing_create)
    async with AsyncSession(placeholder_database, expire_on_commit=False) as session:
        await initialize_agentic_global_variables(session)
        await session.commit()
    assert calls == ["FLOW_ID", "COMPONENT_ID", "FIELD_NAME"]
    assert sorted(await _names(placeholder_database, user.id)) == ["FIELD_NAME", "FLOW_ID"]


async def test_invalidated_connection_reaches_caller_recovery(placeholder_database, monkeypatch):
    await _seed_user(placeholder_database)

    async def invalidated_create(*_args, **_kwargs):
        statement = "INSERT"
        raise DBAPIError(statement, {}, RuntimeError("connection lost"), connection_invalidated=True)

    monkeypatch.setattr(get_variable_service(), "create_variable", invalidated_create)
    async with AsyncSession(placeholder_database, expire_on_commit=False) as session:
        with pytest.raises(DBAPIError, match="connection lost"):
            await initialize_agentic_global_variables(session)
        await session.rollback()


async def test_active_repeatable_read_does_not_duplicate_or_commit_caller_work(placeholder_database):
    if placeholder_database.dialect.name != "postgresql":
        pytest.skip("PostgreSQL isolation levels are required")
    user = await _seed_user(placeholder_database)
    async with AsyncSession(placeholder_database, expire_on_commit=False) as reader:
        connection = await reader.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        await reader.exec(select(func.count(User.id)))  # Fix the snapshot before another worker commits.
        pending_user = User(id=uuid4(), username=f"pending-{uuid4().hex}", password="x", is_active=True)  # noqa: S106
        reader.add(pending_user)
        await reader.flush()
        async with AsyncSession(placeholder_database, expire_on_commit=False) as writer:
            await initialize_agentic_global_variables(writer)
            await writer.commit()

        await initialize_agentic_global_variables(reader)
        assert await connection.get_isolation_level() == "REPEATABLE READ"
        assert reader.in_transaction()  # The initializer must not commit or roll back caller work.
        assert reader.is_active
        await reader.commit()

    assert sorted(await _names(placeholder_database, user.id)) == sorted(GLOBAL_PLACEHOLDER_NAMES)
    assert await _names(placeholder_database, pending_user.id) == []
    async with AsyncSession(placeholder_database) as session:
        assert await session.get(User, pending_user.id) is not None


async def test_startup_and_login_use_the_same_user_lock_order(placeholder_database):
    if placeholder_database.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row locks are required")
    user = await _seed_user(placeholder_database)
    login_holds_user = asyncio.Event()
    startup_lock_attempt = asyncio.Event()

    class StartupSession(AsyncSession):
        async def exec(self, statement, *args, **kwargs):
            if getattr(statement, "_for_update_arg", None) is not None:
                startup_lock_attempt.set()
            return await super().exec(statement, *args, **kwargs)

    async def login():
        async with AsyncSession(placeholder_database, expire_on_commit=False) as session:
            # Environment imports already take this lock before the agentic initializer.
            await session.connection(execution_options={"isolation_level": "READ COMMITTED"})
            await session.get(User, user.id, with_for_update=True)
            login_holds_user.set()
            await startup_lock_attempt.wait()
            await initialize_agentic_user_variables(user.id, session)
            await session.commit()

    async def startup():
        await login_holds_user.wait()
        async with StartupSession(placeholder_database, expire_on_commit=False) as session:
            await initialize_agentic_global_variables(session)
            await session.commit()

    await asyncio.wait_for(asyncio.gather(login(), startup()), timeout=20)
    names = await _names(placeholder_database, user.id)
    assert sorted(names) == sorted([*GLOBAL_PLACEHOLDER_NAMES, "ASTRA_TOKEN"])


@pytest.mark.parametrize("url", ["postgres://host/db", "postgresql://host/db", "postgresql+psycopg://host/db"])
def test_postgres_url_uses_async_psycopg(monkeypatch, url):
    monkeypatch.setenv("LANGFLOW_TEST_POSTGRES_URL", url)
    assert _postgres_url() == "postgresql+psycopg://host/db"


@pytest.mark.parametrize("driver", ["psycopg2", "asyncpg", "pg8000"])
def test_postgres_url_rejects_unsupported_drivers(monkeypatch, driver):
    monkeypatch.setenv("LANGFLOW_TEST_POSTGRES_URL", f"postgresql+{driver}://host/db")
    with pytest.raises(ValueError, match=r"postgresql\+psycopg"):
        _postgres_url()


async def test_global_sweeps_lock_users_in_uuid_order(placeholder_database, monkeypatch):
    first = await _seed_user(placeholder_database)
    second = await _seed_user(placeholder_database)
    observed = []
    service = get_variable_service()
    original = service.existing_variable_name_counts

    async def record_order(user_id, names, session):
        observed.append(user_id)
        return await original(user_id, names, session=session)

    monkeypatch.setattr(service, "existing_variable_name_counts", record_order)
    async with AsyncSession(placeholder_database, expire_on_commit=False) as session:
        await initialize_agentic_global_variables(session)
        await session.commit()
    assert observed == sorted([first.id, second.id])

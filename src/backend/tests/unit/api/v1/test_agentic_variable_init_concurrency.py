"""Concurrent agentic placeholder initialization on SQLite and PostgreSQL.

Set LANGFLOW_TEST_POSTGRES_URL (or LANGFLOW_TEST_DATABASE_URI, as CI does) to a
PostgreSQL URL for a test database whose user can create schemas. Each
PostgreSQL case owns a temporary schema.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from langflow.api.utils.mcp.agentic_mcp import initialize_agentic_global_variables
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_variable_service
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

GLOBAL_PLACEHOLDER_NAMES = ("COMPONENT_ID", "FIELD_NAME", "FLOW_ID")


def _postgres_url() -> str | None:
    url = os.environ.get("LANGFLOW_TEST_POSTGRES_URL") or os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not url or "+psycopg" in url:
        return url
    return url.replace("postgresql://", "postgresql+psycopg://", 1).replace("postgres://", "postgresql+psycopg://", 1)


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


class DelayedFlushSession(AsyncSession):
    """Give a concurrent initializer time to pass a racy existence check."""

    async def flush(self, *args, **kwargs):
        await asyncio.sleep(0.05)
        return await super().flush(*args, **kwargs)


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


async def test_concurrent_workers_create_one_row_per_placeholder(placeholder_database):
    user = await _seed_user(placeholder_database)

    async def worker() -> None:
        async with DelayedFlushSession(placeholder_database, expire_on_commit=False) as session:
            await initialize_agentic_global_variables(session)
            await session.commit()

    await asyncio.wait_for(asyncio.gather(worker(), worker()), timeout=15)

    names = await _names(placeholder_database, user.id)
    assert sorted(names) == sorted(GLOBAL_PLACEHOLDER_NAMES)
    assert all(names.count(name) == 1 for name in GLOBAL_PLACEHOLDER_NAMES)


async def test_integrity_error_savepoint_allows_remaining_creates(placeholder_database, monkeypatch):
    """A conflict on one insert must roll back only that savepoint, not the session."""
    user = await _seed_user(placeholder_database)
    service = get_variable_service()
    original = service.create_variable
    calls = {"n": 0}

    async def flaky_create(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            # Raise from inside the caller's savepoint so the session stays usable.
            statement = "INSERT"
            raise IntegrityError(statement, {}, Exception("duplicate placeholder"))
        return await original(*args, **kwargs)

    monkeypatch.setattr(service, "create_variable", flaky_create)

    async with AsyncSession(placeholder_database, expire_on_commit=False) as session:
        await initialize_agentic_global_variables(session)
        await session.commit()

    names = await _names(placeholder_database, user.id)
    assert "FLOW_ID" not in names or names.count("FLOW_ID") == 1
    # The first created name is FLOW_ID in the startup map; after a savepoint
    # rollback, the remaining placeholders must still be inserted.
    assert "COMPONENT_ID" in names
    assert "FIELD_NAME" in names
    assert all(names.count(name) <= 1 for name in GLOBAL_PLACEHOLDER_NAMES)

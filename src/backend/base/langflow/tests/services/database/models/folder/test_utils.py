"""Tests for ``create_default_folder_if_it_doesnt_exist``.

These tests exist specifically to protect the new deployment-guard pre-check
added by this PR: the guard-facing SELECT must correctly find flows whose
``folder_id`` is NULL so ``ensure_flow_moves_allowed`` is consulted with a
non-empty pair list before the default folder is populated.

The subsequent ``update(Flow)`` statement in ``create_default_folder_if_it_doesnt_exist``
retains its pre-existing upstream behavior and is intentionally out of scope
for this test.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.utils import create_default_folder_if_it_doesnt_exist
from langflow.services.database.models.user.model import User
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _create_sqlite_engine() -> AsyncEngine:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    return _create_sqlite_engine()


@pytest.fixture(name="db")
async def db_fixture(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await db_engine.dispose()


@pytest.fixture
async def user(db: AsyncSession) -> User:
    now = _utcnow_naive()
    row = User(username="guard-user", password=_TEST_PASSWORD, is_active=True, create_at=now, updated_at=now)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.mark.asyncio
async def test_default_folder_creation_consults_guard_with_null_folder_flows(
    db: AsyncSession, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Flows with ``folder_id=NULL`` must be surfaced to the guard.

    Regression: the guard-facing SELECT previously used ``Flow.folder_id is None``,
    which SQLAlchemy compiles to a constant-false predicate and therefore
    returned zero rows even when matching flows existed. This test asserts the
    guard is invoked with the NULL-folder flow included in its input.
    """
    null_folder_flow = Flow(
        name="orphan-flow",
        user_id=user.id,
        folder_id=None,
        data={"nodes": [], "edges": []},
        updated_at=_utcnow_naive(),
    )
    db.add(null_folder_flow)
    await db.commit()
    await db.refresh(null_folder_flow)

    guard_spy = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "langflow.services.database.models.folder.utils.ensure_flow_moves_allowed",
        guard_spy,
    )

    await create_default_folder_if_it_doesnt_exist(db, user.id)

    guard_spy.assert_awaited_once()
    call_kwargs = guard_spy.await_args.kwargs
    flow_folder_pairs = call_kwargs["flow_folder_pairs"]
    flow_ids_seen = {pair[0] for pair in flow_folder_pairs}
    assert null_folder_flow.id in flow_ids_seen, (
        "Guard was not consulted for the NULL-folder flow; the pre-check SELECT is not matching NULL rows."
    )
    for _flow_id, old_folder_id in flow_folder_pairs:
        assert old_folder_id is None

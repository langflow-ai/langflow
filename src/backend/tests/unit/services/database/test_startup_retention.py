"""Startup retention preserves flow partitions and unique build records."""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.utils import clean_transactions, clean_vertex_builds
from sqlalchemy import make_url, schema
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(params=["sqlite", "postgresql"])
async def retention_session(request, tmp_path):
    """Use real models in an isolated SQLite file or PostgreSQL schema."""
    namespace = f"retention_{uuid4().hex}"
    if request.param == "postgresql":
        url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
        if not url:
            pytest.skip("LANGFLOW_TEST_DATABASE_URI is required for PostgreSQL")
        url = make_url(url).set(drivername="postgresql+asyncpg")
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": namespace}})
        async with engine.begin() as connection:
            await connection.execute(schema.CreateSchema(namespace))
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retention.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync: SQLModel.metadata.create_all(
                    sync, tables=[TransactionTable.__table__, VertexBuildTable.__table__]
                )
            )
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
    finally:
        if request.param == "postgresql":
            async with engine.begin() as connection:
                await connection.execute(schema.DropSchema(namespace, cascade=True))
        await engine.dispose()


@pytest.mark.parametrize("limit", [-1, 0, 1, 3, 6])
async def test_startup_transaction_retention_is_per_flow_and_repeatable(retention_session, limit):
    """A busy flow must not evict another flow's transaction history."""
    async_session = retention_session
    flow_ids = [uuid4(), uuid4()]
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ids = []
    for flow_id, count in zip(flow_ids, [5, 2], strict=True):
        rows = [
            TransactionTable(
                id=UUID(int=index + 1 + len(ids) * 10),
                flow_id=flow_id,
                timestamp=timestamp,
                vertex_id="reused",
                status="success",
            )
            for index in range(count)
        ]
        async_session.add_all(rows)
        sorted_ids = sorted((row.id for row in rows), reverse=True)
        ids.append(sorted_ids if limit < 0 else sorted_ids[:limit])
    await async_session.commit()
    settings = SimpleNamespace(settings=SimpleNamespace(max_transactions_to_keep=limit))
    for _ in range(2):
        await clean_transactions(settings, async_session)
        await async_session.commit()
        for flow_id, expected in zip(flow_ids, ids, strict=True):
            remaining = (
                await async_session.exec(select(TransactionTable.id).where(TransactionTable.flow_id == flow_id))
            ).all()
            assert set(remaining) == set(expected)


@pytest.mark.parametrize("limit", [0, 1, 3, 6])
async def test_startup_build_retention_uses_build_id(retention_session, limit):
    """Deleting an old build must not delete newer builds of the same component."""
    async_session = retention_session
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        VertexBuildTable(build_id=UUID(int=i + 1), id="same-vertex", flow_id=uuid4(), valid=True, timestamp=timestamp)
        for i in range(5)
    ]
    async_session.add_all(rows)
    await async_session.commit()
    settings = SimpleNamespace(settings=SimpleNamespace(max_vertex_builds_to_keep=limit))
    expected = {row.build_id for row in rows[-limit:]} if limit else set()
    for _ in range(2):
        await clean_vertex_builds(settings, async_session)
        await async_session.commit()
        remaining = (await async_session.exec(select(VertexBuildTable.build_id))).all()
        assert set(remaining) == expected


async def test_startup_cleanup_can_be_rolled_back(retention_session):
    """Cleanup remains part of its caller's transaction until committed."""
    session = retention_session
    row = TransactionTable(flow_id=uuid4(), vertex_id="vertex", status="success")
    session.add(row)
    await session.commit()
    row_id = row.id
    settings = SimpleNamespace(settings=SimpleNamespace(max_transactions_to_keep=0))
    await clean_transactions(settings, session)
    await session.rollback()
    assert (await session.exec(select(TransactionTable.id))).all() == [row_id]


async def test_startup_retention_orders_timestamp_before_id(retention_session):
    """A larger ID cannot displace a newer record in either history table."""
    session = retention_session
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    flow_id = uuid4()
    for index in range(3):
        timestamp = now + timedelta(seconds=index)
        session.add(
            TransactionTable(
                id=UUID(int=3 - index), flow_id=flow_id, vertex_id="v", timestamp=timestamp, status="success"
            )
        )
        session.add(
            VertexBuildTable(build_id=UUID(int=3 - index), id="v", flow_id=flow_id, timestamp=timestamp, valid=True)
        )
    await session.commit()
    settings = SimpleNamespace(settings=SimpleNamespace(max_transactions_to_keep=1, max_vertex_builds_to_keep=1))
    await clean_transactions(settings, session)
    await clean_vertex_builds(settings, session)
    await session.commit()
    assert (await session.exec(select(TransactionTable.id))).all() == [UUID(int=1)]
    assert (await session.exec(select(VertexBuildTable.build_id))).all() == [UUID(int=1)]


async def test_startup_cleanup_preserves_concurrent_new_flow(retention_session):
    """A row committed after cleanup's snapshot survives its later commit."""
    session = retention_session
    if session.bind.dialect.name != "postgresql":
        pytest.skip("SQLite serializes writers; this exercises PostgreSQL MVCC")
    session.add_all([TransactionTable(flow_id=uuid4(), vertex_id="v", status="success") for _ in range(2)])
    await session.commit()
    settings = SimpleNamespace(settings=SimpleNamespace(max_transactions_to_keep=0))
    await clean_transactions(settings, session)
    async with AsyncSession(session.bind, expire_on_commit=False) as writer:
        row = TransactionTable(flow_id=uuid4(), vertex_id="v", status="success")
        writer.add(row)
        await writer.commit()
        row_id = row.id
    await session.commit()
    assert (await session.exec(select(TransactionTable.id))).all() == [row_id]

"""Rows spilled to the outbox before an upgrade lack the columns added since; a flush must still insert them."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.database.models.transactions.model import TransactionBase, TransactionTable
from langflow.services.telemetry_writer.service import TelemetryWriterService
from sqlalchemy import func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
async def writer_and_engine():
    engine = create_async_engine("sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    writer = TelemetryWriterService(SimpleNamespace(settings=SimpleNamespace(telemetry_writer_enabled=True)))
    writer._engine = engine
    writer._session_maker = async_sessionmaker(engine, expire_on_commit=False)
    writer._started = True
    writer._shutdown_event = asyncio.Event()
    try:
        yield writer, engine
    finally:
        await engine.dispose()


def _row(flow_id, **extra) -> dict:
    base = TransactionBase(
        vertex_id="v1", inputs={"x": 1}, outputs={"y": 2}, status="success", flow_id=flow_id, **extra
    )
    return TransactionTable(**base.model_dump()).model_dump(mode="python")


async def test_should_insert_a_batch_mixing_rows_from_before_and_after_the_upgrade(writer_and_engine) -> None:
    writer, engine = writer_and_engine
    flow_id = uuid4()
    pre_upgrade = _row(flow_id)
    pre_upgrade.pop("user_id")
    pre_upgrade.pop("session_id")
    post_upgrade = _row(flow_id, user_id=uuid4(), session_id="alice::s1")

    await writer._flush([pre_upgrade, post_upgrade], [])

    async with AsyncSession(engine) as session:
        sessions = (await session.exec(select(TransactionTable.session_id))).all()
        count = await session.scalar(select(func.count()).select_from(TransactionTable))
    assert count == 2
    assert sorted(sessions, key=str) == sorted([None, "alice::s1"], key=str)

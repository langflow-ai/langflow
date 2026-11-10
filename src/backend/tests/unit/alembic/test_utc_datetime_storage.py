"""Application writes and queries remain compatible after the UTC migration."""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from alembic import command
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.user.model import User, UserUpdate
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.tracing import repository
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_UTC = datetime(2024, 11, 3, 8, 30, 12, 345678, tzinfo=timezone.utc)


@pytest.fixture
def migrated_engine(db_url):  # noqa: F811
    command.upgrade(_make_alembic_cfg(db_url), "head")
    engine = sa.create_engine(_engine_url(db_url))
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "timestamp",
    [
        _UTC.replace(tzinfo=None),
        _UTC.replace(tzinfo=None).isoformat(),
        _UTC.astimezone(timezone(timedelta(hours=-7))).isoformat(),
    ],
    ids=["legacy-datetime", "legacy-string", "offset-string"],
)
def test_legacy_inputs_and_default_writes_roundtrip_in_utc(migrated_engine, timestamp):
    with Session(migrated_engine) as session:
        user = User(username="utc-test", password="hashed-test-value")  # noqa: S106
        session.add(user)
        session.flush()
        flow = Flow.model_validate({"name": "UTC flow", "user_id": user.id, "updated_at": timestamp})
        session.add(flow)
        session.flush()
        message = MessageTable.model_validate(
            {
                "timestamp": timestamp,
                "sender": "User",
                "sender_name": "User",
                "session_id": "utc-test",
                "text": "hello",
                "files": [],
                "category": "message",
                "flow_id": flow.id,
            }
        )
        transaction = TransactionTable(vertex_id="test", status="success", flow_id=flow.id)
        vertex = VertexBuildTable(id="test", valid=True, flow_id=flow.id)
        session.add_all([message, transaction, vertex])
        user.sqlmodel_update(UserUpdate(last_login_at=timestamp).model_dump(exclude_unset=True))
        session.commit()
        for record, field in [(flow, "updated_at"), (message, "timestamp"), (user, "last_login_at")]:
            session.refresh(record)
            assert getattr(record, field) == _UTC
            assert getattr(record, field).utcoffset() == timedelta(0)
        for record in [transaction, vertex]:
            session.refresh(record)
            assert record.timestamp.utcoffset() == timedelta(0)
        assert message.model_dump(mode="json")["timestamp"] == "2024-11-03 08:30:12.345678 UTC"
        assert flow.model_dump(mode="json")["updated_at"] == "2024-11-03T08:30:12+00:00"
        assert UserUpdate(last_login_at=None).last_login_at is None


@pytest.mark.asyncio
async def test_trace_filters_accept_legacy_naive_datetimes(db_url, migrated_engine, monkeypatch):  # noqa: F811
    with Session(migrated_engine) as session:
        user = User(username="trace-test", password="hashed-test-value")  # noqa: S106
        session.add(user)
        session.flush()
        flow = Flow(name="Trace flow", user_id=user.id)
        session.add(flow)
        session.flush()
        trace = TraceTable(name="inside range", flow_id=flow.id, start_time=_UTC)
        outside = TraceTable(name="outside range", flow_id=flow.id, start_time=_UTC + timedelta(hours=1))
        session.add_all([trace, outside])
        session.commit()
        user_id, flow_id, trace_id = user.id, flow.id, trace.id

    engine = create_async_engine(db_url)

    @asynccontextmanager
    async def database_session():
        async with AsyncSession(engine) as session:
            yield session

    monkeypatch.setattr(repository, "session_scope", database_session)
    try:
        for timestamp in [_UTC.replace(tzinfo=None), _UTC.astimezone(timezone(timedelta(hours=5)))]:
            result = await repository.fetch_traces(user_id, flow_id, None, None, None, timestamp, timestamp, 1, 50)
            assert result.total == 1
            assert result.traces[0].id == trace_id
            assert result.traces[0].start_time == _UTC
            assert result.traces[0].start_time.utcoffset() == timedelta(0)
    finally:
        await engine.dispose()

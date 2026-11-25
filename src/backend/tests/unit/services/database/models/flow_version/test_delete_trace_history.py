"""Exercise flow deletion against real trace histories."""

import os
from uuid import UUID, uuid4

import pytest
from langflow.api.utils.flow_utils import cascade_delete_flow
from langflow.services.database.models import Flow, MessageTable, SpanTable, TraceTable, User
from langflow.services.database.models.traces.model import SpanStatus
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.sql.dml import Delete
from sqlmodel import SQLModel, insert, select, text
from sqlmodel.ext.asyncio.session import AsyncSession

_POSTGRES = pytest.param("postgresql", marks=pytest.mark.real_services)
_POSTGRES_BIND_LIMIT = 65_535
_BATCH_SIZE = 4_000


@pytest.fixture
async def trace_engine(request) -> AsyncEngine:
    if request.param == "sqlite":
        engine = create_async_engine("sqlite+aiosqlite://")
        try:
            async with engine.begin() as connection:
                assert await connection.scalar(text("PRAGMA foreign_keys")) == 0
                await connection.run_sync(SQLModel.metadata.create_all)
            yield engine
        finally:
            await engine.dispose()
        return

    raw_url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not raw_url or make_url(raw_url).get_backend_name() != "postgresql":
        pytest.skip("LANGFLOW_TEST_DATABASE_URI must point to PostgreSQL")
    url = make_url(raw_url).set(drivername="postgresql+psycopg")
    schema = f"trace_delete_{uuid4().hex}"
    engine = create_async_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.run_sync(SQLModel.metadata.create_all)
        yield engine
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


@pytest.fixture
async def db(trace_engine):
    async with AsyncSession(trace_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
async def flow_ids(db):
    async with db.begin():
        owners = [
            User(username=name, password="unused")  # noqa: S106  # pragma: allowlist secret
            for name in ("target", "other")
        ]
        db.add_all(owners)
        await db.flush()
        target, other = (Flow(name=owner.username, user_id=owner.id) for owner in owners)
        db.add_all([target, other])
    return target.id, other.id


async def _add_trace(db: AsyncSession, flow_id: UUID) -> tuple[UUID, set[UUID]]:
    trace = TraceTable(name="trace", flow_id=flow_id)
    db.add(trace)
    await db.flush()
    parent = SpanTable(name="parent", trace_id=trace.id)
    db.add(parent)
    await db.flush()
    child = SpanTable(name="child", trace_id=trace.id, parent_span_id=parent.id)
    db.add(child)
    await db.flush()
    return trace.id, {parent.id, child.id}


async def _trace_history_size(db: AsyncSession) -> int:
    if db.get_bind().dialect.name != "sqlite":
        return _POSTGRES_BIND_LIMIT + 1
    # Some SQLite builds raise the default limit. Seed enough rows to reproduce on those builds too.
    options = (await db.exec(text("PRAGMA compile_options"))).scalars()
    limit = next(
        (int(option.split("=")[1]) for option in options if option.startswith("MAX_VARIABLE_NUMBER=")),
        _POSTGRES_BIND_LIMIT,
    )
    return max(_POSTGRES_BIND_LIMIT, limit) + 1


async def _assert_rows(db: AsyncSession, *, flows: set[UUID], traces: set[UUID], spans: set[UUID]) -> None:
    assert set((await db.exec(select(Flow.id))).all()) == flows
    assert set((await db.exec(select(TraceTable.id))).all()) == traces
    assert set((await db.exec(select(SpanTable.id))).all()) == spans


class TestCascadeDeleteFlow:
    @pytest.mark.parametrize("trace_engine", ["sqlite", _POSTGRES], indirect=True)
    @pytest.mark.parametrize("large_history", [False, True], ids=["empty", "over-bind-limit"])
    async def test_preserves_unrelated_trace_history(self, db, flow_ids, large_history):
        target, other = flow_ids
        async with db.begin():
            other_trace, other_spans = await _add_trace(db, other)
            if large_history:
                await _add_trace(db, target)
                remaining = await _trace_history_size(db) - 1
                row = {"flow_id": target, "name": "past run", "status": SpanStatus.UNSET}
                for start in range(0, remaining, _BATCH_SIZE):
                    await db.exec(insert(TraceTable), params=[row] * min(_BATCH_SIZE, remaining - start))

        async with db.begin():
            assert await cascade_delete_flow(db, target)

        await _assert_rows(db, flows={other}, traces={other_trace}, spans=other_spans)

    @pytest.mark.parametrize("trace_engine", ["sqlite", _POSTGRES], indirect=True)
    async def test_rolls_back_earlier_deletes(self, db, flow_ids):
        target, other = flow_ids
        async with db.begin():
            target_trace, target_spans = await _add_trace(db, target)
            other_trace, other_spans = await _add_trace(db, other)
            message = MessageTable(
                flow_id=target, sender="user", sender_name="User", session_id="session", text="input"
            )
            db.add(message)
            await db.flush()
            message_id = message.id
            if db.get_bind().dialect.name == "postgresql":
                await db.exec(text("CREATE TABLE trace_delete_blocker (trace_id UUID REFERENCES trace(id))"))
                await db.exec(
                    text("INSERT INTO trace_delete_blocker (trace_id) VALUES (:trace_id)").bindparams(
                        trace_id=target_trace
                    )
                )
            else:
                await db.exec(
                    text(
                        "CREATE TRIGGER trace_delete_blocker BEFORE DELETE ON trace "
                        "BEGIN SELECT RAISE(ABORT, 'trace_delete_blocker'); END"
                    )
                )

        with pytest.raises(RuntimeError, match="Unable to cascade delete flow") as exc:
            async with db.begin():
                await cascade_delete_flow(db, target)

        if db.get_bind().dialect.name == "postgresql":
            assert isinstance(exc.value.__cause__, IntegrityError)
        assert "trace_delete_blocker" in str(exc.value.__cause__)
        await _assert_rows(
            db, flows={target, other}, traces={target_trace, other_trace}, spans=target_spans | other_spans
        )
        assert (await db.exec(select(MessageTable.id))).all() == [message_id]

    @pytest.mark.parametrize("trace_engine", [_POSTGRES], indirect=True)
    async def test_removes_trace_inserted_during_deletion(self, db, flow_ids, trace_engine, monkeypatch):
        target, other = flow_ids
        async with db.begin():
            await _add_trace(db, target)
            other_trace, other_spans = await _add_trace(db, other)

        original_exec = db.exec
        inserted = []

        async def insert_after_span_delete(statement, *args, **kwargs):
            result = await original_exec(statement, *args, **kwargs)
            if isinstance(statement, Delete) and statement.table.name == SpanTable.__tablename__:
                async with AsyncSession(trace_engine) as writer, writer.begin():
                    trace_id, _ = await _add_trace(writer, target)
                inserted.append(trace_id)
            return result

        monkeypatch.setattr(db, "exec", insert_after_span_delete)
        async with db.begin():
            assert await cascade_delete_flow(db, target)

        assert len(inserted) == 1
        await _assert_rows(db, flows={other}, traces={other_trace}, spans=other_spans)

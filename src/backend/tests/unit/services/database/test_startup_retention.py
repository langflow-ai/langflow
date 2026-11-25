"""Startup cleanup keeps the same history the runtime retention sweeper keeps."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from alembic import command
from langflow.services.database.models.transactions import crud as transaction_crud
from langflow.services.database.models.transactions.model import TransactionBase, TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.telemetry_writer import service as writer_module
from langflow.services.utils import clean_transactions, clean_vertex_builds
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from tests.unit.alembic.test_migration_execution import (
    _create_pg_test_database,
    _drop_pg_test_database,
    _make_alembic_cfg,
    _pg_url,
)
from tests.unit.services.telemetry_writer.test_service import _build_writer

_STAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)
_FLOWS = [UUID(int=0xA), UUID(int=0xB), UUID(int=0xC)]
_VERTICES = ["ChatInput-abc", "Agent-def", "ChatOutput-ghi"]


@pytest.fixture(scope="module", params=["sqlite", "postgres"])
def migrated_url(request):
    """A database migrated to head, once per backend for the whole module."""
    if request.param == "sqlite":
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        url = f"sqlite+aiosqlite:///{db_path}"
        command.upgrade(_make_alembic_cfg(url), "head")
        yield url
        for suffix in ("", "-wal", "-shm", "-journal"):
            Path(db_path + suffix).unlink(missing_ok=True)
        return
    base_url = _pg_url()
    if base_url is None:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI not set")
    db_name = f"lf_startup_retention_{uuid4().hex[:12]}"
    url = _create_pg_test_database(base_url, db_name)
    command.upgrade(_make_alembic_cfg(url), "head")
    yield url
    _drop_pg_test_database(base_url, db_name)


@pytest.fixture
async def maker(migrated_url):
    engine = create_async_engine(migrated_url)
    async with engine.begin() as connection:
        await connection.execute(delete(TransactionTable))
        await connection.execute(delete(VertexBuildTable))
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


def _settings(*, transactions: int = 3000, builds: int = 3000, per_vertex: int = 50) -> SimpleNamespace:
    return SimpleNamespace(
        settings=SimpleNamespace(
            max_transactions_to_keep=transactions,
            max_vertex_builds_to_keep=builds,
            max_vertex_builds_per_vertex=per_vertex,
        )
    )


def _transactions(counts: list[int], *, tied: bool) -> list[TransactionTable]:
    return [
        TransactionTable(
            id=UUID(int=(flow_index + 1) * 1000 + i),
            flow_id=_FLOWS[flow_index],
            vertex_id="Agent-def",
            status="success",
            timestamp=_STAMP if tied else _STAMP + timedelta(seconds=i),
        )
        for flow_index, count in enumerate(counts)
        for i in range(count)
    ]


def _builds(runs: list[int], *, tied: bool) -> list[VertexBuildTable]:
    """One row per vertex per run; every run of every flow reuses the same vertex ids."""
    return [
        VertexBuildTable(
            build_id=UUID(int=(flow_index + 1) * 100_000 + run * 10 + vertex_index),
            id=vertex_id,
            flow_id=_FLOWS[flow_index],
            valid=True,
            timestamp=_STAMP if tied else _STAMP + timedelta(seconds=run),
        )
        for flow_index, run_count in enumerate(runs)
        for run in range(run_count)
        for vertex_index, vertex_id in enumerate(_VERTICES)
    ]


def _expected_transactions(rows: list[TransactionTable], limit: int) -> set[UUID]:
    if limit < 0:
        return {row.id for row in rows}
    kept: set[UUID] = set()
    for flow_id in {row.flow_id for row in rows}:
        flow_rows = sorted((r for r in rows if r.flow_id == flow_id), key=lambda r: (r.timestamp, r.id), reverse=True)
        kept |= {row.id for row in flow_rows[:limit]}
    return kept


def _expected_builds(rows: list[VertexBuildTable], *, builds: int, per_vertex: int) -> set[UUID]:
    def newest_first(items):
        return sorted(items, key=lambda r: (r.timestamp, r.build_id), reverse=True)

    survivors = list(rows)
    if per_vertex >= 0:
        survivors = []
        for key in {(row.flow_id, row.id) for row in rows}:
            survivors += newest_first(r for r in rows if (r.flow_id, r.id) == key)[:per_vertex]
    if builds >= 0:
        survivors = newest_first(survivors)[:builds]
    return {row.build_id for row in survivors}


async def _seed(maker, rows) -> None:
    async with maker() as session:
        session.add_all(rows)
        await session.commit()


async def _restart_cleanup(maker, settings) -> None:
    async with maker() as session:
        await clean_transactions(settings, session)
        await clean_vertex_builds(settings, session)
        await session.commit()


async def _surviving_ids(maker) -> tuple[set[UUID], set[UUID]]:
    async with maker() as session:
        transactions = set((await session.execute(select(TransactionTable.id))).scalars())
        builds = set((await session.execute(select(VertexBuildTable.build_id))).scalars())
    return transactions, builds


@pytest.mark.parametrize("tied", [False, True], ids=["distinct", "tied"])
@pytest.mark.parametrize("limit", [-1, 0, 2, 3, 4], ids=lambda v: f"limit{v}")
async def test_should_keep_newest_transactions_per_flow_when_startup_cleanup_runs_twice(maker, limit, tied):
    rows = _transactions([5, 3, 2], tied=tied)
    expected = _expected_transactions(rows, limit)
    await _seed(maker, rows)

    for _ in range(2):
        await _restart_cleanup(maker, _settings(transactions=limit))
        transactions, _builds_left = await _surviving_ids(maker)
        assert transactions == expected


async def test_should_not_evict_quiet_flow_transactions_when_busy_flow_exceeds_cap(maker):
    rows = _transactions([6, 2, 0], tied=False)
    await _seed(maker, rows)

    await _restart_cleanup(maker, _settings(transactions=3))

    transactions, _builds_left = await _surviving_ids(maker)
    assert transactions == {UUID(int=1003), UUID(int=1004), UUID(int=1005), UUID(int=2000), UUID(int=2001)}


async def test_should_keep_newest_builds_when_vertex_ids_repeat_across_builds(maker):
    rows = _builds([30, 0, 0], tied=False)
    await _seed(maker, rows)

    await _restart_cleanup(maker, _settings(builds=6, per_vertex=50))

    _transactions_left, builds = await _surviving_ids(maker)
    assert builds == {UUID(int=100_000 + run * 10 + v) for run in (28, 29) for v in range(3)}


@pytest.mark.parametrize("tied", [False, True], ids=["distinct", "tied"])
@pytest.mark.parametrize(
    ("builds", "per_vertex"),
    [(-1, -1), (0, 50), (6, 50), (27, 50), (28, 50), (100, 2), (5, 2), (100, -1), (-1, 3)],
    ids=lambda v: str(v),
)
async def test_should_keep_newest_builds_per_vertex_and_globally_when_startup_cleanup_runs_twice(
    maker, builds, per_vertex, tied
):
    rows = _builds([4, 3, 2], tied=tied)
    expected = _expected_builds(rows, builds=builds, per_vertex=per_vertex)
    await _seed(maker, rows)

    for _ in range(2):
        await _restart_cleanup(maker, _settings(builds=builds, per_vertex=per_vertex))
        _transactions_left, survivors = await _surviving_ids(maker)
        assert survivors == expected


@pytest.mark.parametrize("tied", [False, True], ids=["distinct", "tied"])
async def test_should_keep_same_rows_as_runtime_sweeper_when_caps_are_exceeded(maker, monkeypatch, tied):
    async def not_paused() -> bool:
        return False

    monkeypatch.setattr(writer_module, "writes_paused", not_paused)
    caps = {"max_transactions_to_keep": 3, "max_vertex_builds_to_keep": 10, "max_vertex_builds_per_vertex": 2}
    # Reverse insertion order so a tie can only resolve one way through the ordering, not the heap.
    transaction_rows = list(reversed(_transactions([5, 3, 2], tied=tied)))
    build_rows = list(reversed(_builds([4, 3, 2], tied=tied)))

    await _seed(maker, [TransactionTable(**r.model_dump()) for r in transaction_rows])
    await _seed(maker, [VertexBuildTable(**r.model_dump()) for r in build_rows])
    writer = _build_writer(caps)
    writer._session_maker = maker
    writer._dirty_tx_flows = {str(flow) for flow in _FLOWS}
    writer._dirty_vb_flows = {str(flow) for flow in _FLOWS}
    await writer._run_retention_pass()
    runtime = await _surviving_ids(maker)
    assert runtime == (
        _expected_transactions(transaction_rows, caps["max_transactions_to_keep"]),
        _expected_builds(build_rows, builds=caps["max_vertex_builds_to_keep"], per_vertex=2),
    )

    async with maker() as session:
        await session.execute(delete(TransactionTable))
        await session.execute(delete(VertexBuildTable))
        await session.commit()
    await _seed(maker, transaction_rows)
    await _seed(maker, build_rows)
    await _restart_cleanup(
        maker,
        _settings(
            transactions=caps["max_transactions_to_keep"],
            builds=caps["max_vertex_builds_to_keep"],
            per_vertex=caps["max_vertex_builds_per_vertex"],
        ),
    )

    assert await _surviving_ids(maker) == runtime


async def test_should_break_timestamp_ties_by_id_when_direct_write_path_prunes_transactions(maker, monkeypatch):
    monkeypatch.setattr(transaction_crud, "get_settings_service", lambda: _settings(transactions=3))
    await _seed(maker, list(reversed(_transactions([5, 0, 0], tied=True))))
    newest = TransactionBase(
        flow_id=_FLOWS[0], vertex_id="Agent-def", status="success", timestamp=_STAMP + timedelta(seconds=1)
    )

    async with maker() as session:
        logged = await transaction_crud.log_transaction(session, newest)

    transactions, _builds_left = await _surviving_ids(maker)
    tied_survivors = transactions - {logged.id}
    # Only the tie-break is asserted; how many rows this path keeps is its own existing contract.
    assert tied_survivors
    assert tied_survivors == {UUID(int=1004 - i) for i in range(len(tied_survivors))}

"""Tests for TelemetryWriterService.

The service is exercised end-to-end against a real in-memory SQLite database
(no mocking of the persistence layer). We bypass ``start()`` in most tests so
we don't have to bring up the entire langflow service manager — instead each
test wires up the writer's internals directly against the test
``async_session`` fixture's engine.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from langflow.services.database.models.transactions.model import TransactionBase, TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildBase, VertexBuildTable
from langflow.services.telemetry_writer.service import TelemetryWriterService
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel


class _FakeSettings:
    """Mutable settings stand-in.

    Real ``Settings`` is a pydantic-settings model whose constructor kwargs are
    overridden by env-var sources; tests can't reliably set fields through it.
    A plain object with the attributes the writer reads via ``getattr`` is
    sufficient and side-steps that quirk.
    """

    def __init__(self, **overrides):
        defaults = {
            "telemetry_writer_enabled": True,
            "telemetry_writer_batch_size": 200,
            "telemetry_writer_flush_interval_s": 0.5,
            "telemetry_writer_cleanup_interval_s": 60,
            "telemetry_writer_max_queue": 100_000,
            "telemetry_writer_outbox_dir": None,
            "telemetry_writer_shutdown_drain_s": 5.0,
            "max_transactions_to_keep": 3000,
            "max_vertex_builds_to_keep": 3000,
            "max_vertex_builds_per_vertex": 50,
        }
        for key, value in {**defaults, **overrides}.items():
            setattr(self, key, value)


class _FakeSettingsService:
    def __init__(self, **overrides):
        self.settings = _FakeSettings(**overrides)


def _build_writer(settings_overrides=None) -> TelemetryWriterService:
    return TelemetryWriterService(_FakeSettingsService(**(settings_overrides or {})))


def _make_transaction_row(flow_id, vertex_id="v1") -> dict:
    base = TransactionBase(
        vertex_id=vertex_id,
        target_id=None,
        inputs={"x": 1},
        outputs={"y": 2},
        status="success",
        error=None,
        flow_id=flow_id,
    )
    return TransactionTable(**base.model_dump()).model_dump(mode="python")


def _make_vertex_build_row(flow_id, vertex_id="v1") -> dict:
    base = VertexBuildBase(
        id=vertex_id,
        flow_id=flow_id,
        valid=True,
        params="p",
        data={"r": 1},
        artifacts=None,
    )
    return VertexBuildTable(**base.model_dump()).model_dump(mode="python")


@pytest.fixture
async def writer_with_engine():
    """Yield (writer, engine) wired together with a fresh in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    writer = _build_writer()
    writer._engine = engine
    writer._session_maker = async_sessionmaker(engine, expire_on_commit=False)
    writer._started = True
    writer._shutdown_event = asyncio.Event()
    try:
        yield writer, engine
    finally:
        writer._started = False
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
        await engine.dispose()


def test_is_enabled_reads_settings() -> None:
    enabled = _build_writer({"telemetry_writer_enabled": True})
    disabled = _build_writer({"telemetry_writer_enabled": False})
    assert enabled.is_enabled() is True
    assert disabled.is_enabled() is False


def test_enqueue_when_not_running_returns_false() -> None:
    writer = _build_writer()
    assert writer.enqueue_transaction({"any": "thing"}) is False
    assert writer.enqueue_vertex_build({"any": "thing"}) is False


def test_enqueue_when_running_buffers_payload(writer_with_engine) -> None:
    writer, _ = writer_with_engine
    payload = {"flow_id": str(uuid4()), "vertex_id": "v1"}
    assert writer.enqueue_transaction(payload) is True
    assert len(writer._tx_buffer) == 1
    assert writer.enqueued_transactions == 1


def test_overflow_drops_oldest(writer_with_engine) -> None:
    writer, _ = writer_with_engine
    writer.settings_service.settings.telemetry_writer_max_queue = 3
    for i in range(5):
        writer.enqueue_transaction({"i": i})
    # Cap is 3 → oldest two dropped, newest three retained.
    assert len(writer._tx_buffer) == 3
    assert writer.dropped_transactions == 2
    assert [item["i"] for item in writer._tx_buffer] == [2, 3, 4]


async def test_flush_inserts_transactions_and_vertex_builds(writer_with_engine) -> None:
    writer, engine = writer_with_engine
    flow_id = uuid4()
    tx_batch = [_make_transaction_row(flow_id) for _ in range(5)]
    vb_batch = [_make_vertex_build_row(flow_id) for _ in range(3)]

    await writer._flush(tx_batch, vb_batch)

    async with AsyncSession(engine) as session:
        tx_count = await session.scalar(select(func.count()).select_from(TransactionTable))
        vb_count = await session.scalar(select(func.count()).select_from(VertexBuildTable))
    assert tx_count == 5
    assert vb_count == 3
    # Sweeper-driven retention requires dirty-flow tracking; flush populates it.
    assert str(flow_id) in writer._dirty_tx_flows
    assert str(flow_id) in writer._dirty_vb_flows


async def test_retention_sweep_caps_transactions_per_flow(writer_with_engine) -> None:
    writer, engine = writer_with_engine
    writer.settings_service.settings.max_transactions_to_keep = 3
    flow_id = uuid4()
    tx_batch = [_make_transaction_row(flow_id) for _ in range(10)]
    await writer._flush(tx_batch, [])
    async with AsyncSession(engine) as session:
        before = await session.scalar(select(func.count()).select_from(TransactionTable))
    assert before == 10

    await writer._run_retention_pass()

    async with AsyncSession(engine) as session:
        after = await session.scalar(select(func.count()).select_from(TransactionTable))
    assert after == 3


async def test_retention_sweep_caps_vertex_builds_globally(writer_with_engine) -> None:
    writer, engine = writer_with_engine
    writer.settings_service.settings.max_vertex_builds_to_keep = 4
    writer.settings_service.settings.max_vertex_builds_per_vertex = 50
    flow_id = uuid4()
    vb_batch = [_make_vertex_build_row(flow_id, vertex_id=f"v{i}") for i in range(8)]
    await writer._flush([], vb_batch)
    await writer._run_retention_pass()

    async with AsyncSession(engine) as session:
        count = await session.scalar(select(func.count()).select_from(VertexBuildTable))
    assert count == 4


async def test_writer_loop_drains_buffers(writer_with_engine) -> None:
    writer, engine = writer_with_engine
    writer.settings_service.settings.telemetry_writer_batch_size = 2
    writer.settings_service.settings.telemetry_writer_flush_interval_s = 0.01
    flow_id = uuid4()
    for _ in range(5):
        writer.enqueue_transaction(_make_transaction_row(flow_id))
        writer.enqueue_vertex_build(_make_vertex_build_row(flow_id))

    task = asyncio.create_task(writer._run_writer())
    # Give the writer time to flush all batches.
    for _ in range(20):
        await asyncio.sleep(0.05)
        if not writer._tx_buffer and not writer._vb_buffer:
            break
    writer._shutdown_event.set()
    await asyncio.wait_for(task, timeout=2)

    async with AsyncSession(engine) as session:
        tx_count = await session.scalar(select(func.count()).select_from(TransactionTable))
        vb_count = await session.scalar(select(func.count()).select_from(VertexBuildTable))
    assert tx_count == 5
    assert vb_count == 5
    assert writer.failed_batches == 0


def test_spill_and_restore_round_trip(tmp_path: Path) -> None:
    writer = _build_writer()
    own_dir = tmp_path / str(12345)
    own_dir.mkdir()

    # Producer-side fills in-memory buffer.
    writer._tx_buffer.extend([{"i": 1}, {"i": 2}])
    writer._vb_buffer.extend([{"j": 1}])

    writer._spill_to_disk(own_dir, kind="transactions", buffer=writer._tx_buffer)
    writer._spill_to_disk(own_dir, kind="vertex_builds", buffer=writer._vb_buffer)
    assert not writer._tx_buffer
    assert not writer._vb_buffer

    # New writer comes up against the same outbox directory and restores.
    writer2 = _build_writer()
    writer2._restore_from_disk(own_dir, kind="transactions", buffer=writer2._tx_buffer)
    writer2._restore_from_disk(own_dir, kind="vertex_builds", buffer=writer2._vb_buffer)
    assert list(writer2._tx_buffer) == [{"i": 1}, {"i": 2}]
    assert list(writer2._vb_buffer) == [{"j": 1}]


def _find_dead_pid(start: int = 99_999, max_checks: int = 50_000) -> int:
    from langflow.services.telemetry_writer.service import _pid_alive

    pid = start
    for _ in range(max_checks):
        if not _pid_alive(pid):
            return pid
        pid += 1
    pytest.fail("Unable to find an unused PID for orphan outbox setup")
    return 0  # unreachable, for type-checkers


def test_adopt_orphan_outboxes(tmp_path: Path) -> None:
    # Simulate a dead worker that left rows in a sibling outbox.
    dead_pid = _find_dead_pid()
    dead_dir = tmp_path / str(dead_pid)
    dead_dir.mkdir()
    spill_writer = _build_writer()
    spill_writer._tx_buffer.extend([{"orphan": True}])
    spill_writer._vb_buffer.extend([{"orphan_vb": True}])
    spill_writer._spill_to_disk(dead_dir, kind="transactions", buffer=spill_writer._tx_buffer)
    spill_writer._spill_to_disk(dead_dir, kind="vertex_builds", buffer=spill_writer._vb_buffer)

    own_writer = _build_writer()
    own_writer._adopt_orphan_outboxes(tmp_path, own_pid=1)
    assert list(own_writer._tx_buffer) == [{"orphan": True}]
    assert list(own_writer._vb_buffer) == [{"orphan_vb": True}]
    # Orphan directory was cleaned up.
    assert not dead_dir.exists()


def test_adopt_orphan_outboxes_honors_max_queue(tmp_path: Path) -> None:
    """A pathologically large orphan spill must not OOM the current worker.

    Regression for the case where ``_restore_from_disk`` and
    ``_adopt_orphan_outboxes`` appended directly to the deque, bypassing the
    queue cap.
    """
    dead_pid = _find_dead_pid()
    dead_dir = tmp_path / str(dead_pid)
    dead_dir.mkdir()
    spill_writer = _build_writer()
    # Spill more rows than the receiving writer's cap.
    spill_writer._tx_buffer.extend([{"i": i} for i in range(100)])
    spill_writer._spill_to_disk(dead_dir, kind="transactions", buffer=spill_writer._tx_buffer)

    own_writer = _build_writer({"telemetry_writer_max_queue": 10})
    own_writer._adopt_orphan_outboxes(tmp_path, own_pid=1)

    # Buffer capped at 10; older rows dropped, drop counter reflects loss.
    assert len(own_writer._tx_buffer) == 10
    assert own_writer.dropped_transactions == 90
    # The newest rows (90..99) survive.
    assert [r["i"] for r in own_writer._tx_buffer] == list(range(90, 100))


async def test_sanitization_survives_writer_round_trip(writer_with_engine) -> None:
    """A sensitive value passed through the producer must land redacted in the DB."""
    writer, engine = writer_with_engine
    flow_id = uuid4()
    # TransactionBase.__init__ runs sanitize_data on inputs/outputs. The
    # writer path serializes via model_dump and bulk-inserts; verify the
    # sanitization isn't lost along the way.
    base = TransactionBase(
        vertex_id="v1",
        target_id=None,
        inputs={"api_key": "sk-very-secret-token-12345"},  # pragma: allowlist secret
        outputs={"password": "hunter2"},  # pragma: allowlist secret
        status="success",
        error=None,
        flow_id=flow_id,
    )
    row = TransactionTable(**base.model_dump()).model_dump(mode="python")
    await writer._flush([row], [])

    async with AsyncSession(engine) as session:
        result = await session.execute(select(TransactionTable.inputs, TransactionTable.outputs))
        inputs, outputs = result.one()
    assert "sk-very-secret-token-12345" not in str(inputs)
    assert "hunter2" not in str(outputs)
    assert "api_key" in inputs
    assert "password" in outputs


async def test_retention_failure_preserves_dirty_flows(writer_with_engine) -> None:
    """A sweep that crashes before commit must leave the dirty-flow set intact."""
    writer, _ = writer_with_engine
    tx_flow = uuid4()
    vb_flow = uuid4()
    writer._dirty_tx_flows.add(str(tx_flow))
    writer._dirty_vb_flows.add(str(vb_flow))

    # Wrap the real session_maker so commit raises but execute() works
    # normally — this drives the retention pass through every query and only
    # fails at the commit boundary, which is exactly the scenario the snapshot/
    # restore logic guards against.
    real_session_maker = writer._session_maker

    class _CommitFailsSessionMaker:
        def __call__(self_inner):  # noqa: N805
            session = real_session_maker()

            class _CommitFailsCM:
                async def __aenter__(self):
                    self._session = await session.__aenter__()
                    original_commit = self._session.commit

                    async def _raise_on_commit():
                        await original_commit()  # exercise the path
                        msg = "boom"
                        raise RuntimeError(msg)

                    self._session.commit = _raise_on_commit
                    return self._session

                async def __aexit__(self, *args):
                    return await session.__aexit__(*args)

            return _CommitFailsCM()

    writer._session_maker = _CommitFailsSessionMaker()
    with pytest.raises(RuntimeError, match="boom"):
        await writer._run_retention_pass()

    # Dirty set must still hold both ids since the commit never landed.
    assert str(tx_flow) in writer._dirty_tx_flows
    assert str(vb_flow) in writer._dirty_vb_flows


async def test_in_flight_batch_returned_on_cancel(writer_with_engine) -> None:
    """If the writer is cancelled mid-flush, popped rows must go back to the buffer."""
    writer, _ = writer_with_engine
    writer.settings_service.settings.telemetry_writer_batch_size = 100
    writer.settings_service.settings.telemetry_writer_flush_interval_s = 0.01
    flow_id = uuid4()
    for _ in range(20):
        writer.enqueue_transaction(_make_transaction_row(flow_id))
    assert len(writer._tx_buffer) == 20

    # Replace the session_maker with one that hangs forever inside execute,
    # so the writer is guaranteed to be blocked mid-flush when we cancel.
    hang = asyncio.Event()  # never set

    class _HangingSessionMaker:
        def __call__(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def execute(self, *_):
            await hang.wait()

        async def commit(self):
            pass

    writer._session_maker = _HangingSessionMaker()
    task = asyncio.create_task(writer._run_writer())
    # Give the writer a tick to drain into a batch and start the flush.
    for _ in range(20):
        await asyncio.sleep(0.02)
        if len(writer._tx_buffer) == 0:
            break
    assert len(writer._tx_buffer) == 0  # the batch is in-flight

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Cancelled mid-flush — the 20 rows should be back in the buffer.
    assert len(writer._tx_buffer) == 20


async def test_lifecycle_idempotent_when_disabled() -> None:
    writer = _build_writer({"telemetry_writer_enabled": False})
    # start() is a no-op when disabled.
    await writer.start()
    assert writer.is_running() is False
    # teardown() on a never-started writer is harmless.
    await writer.teardown()


async def test_teardown_spills_remaining_buffer(tmp_path: Path) -> None:
    outbox = tmp_path / "outbox"
    writer = _build_writer(
        {
            "telemetry_writer_outbox_dir": str(outbox),
        }
    )
    # Manually wire enough state to exercise teardown's spill path without
    # going through start() (which needs the full langflow service stack).
    writer._started = True
    writer._shutdown_event = asyncio.Event()
    writer._shutdown_event.set()
    writer._own_outbox_dir = outbox / "1"
    writer._own_outbox_dir.mkdir(parents=True)
    writer._tx_buffer.append({"to_disk": 1})

    await writer.teardown()

    # A second writer pointed at the same dir should see the spilled row.
    writer2 = _build_writer()
    writer2._restore_from_disk(outbox / "1", kind="transactions", buffer=writer2._tx_buffer)
    assert list(writer2._tx_buffer) == [{"to_disk": 1}]

    # Clean up the diskcache directory tree.
    shutil.rmtree(outbox, ignore_errors=True)
    # Also clean up our potential tempfile fallback if used.
    fallback = Path(tempfile.gettempdir()) / "langflow_telemetry_outbox"
    if fallback.exists() and fallback.is_dir() and not any(fallback.iterdir()):
        fallback.rmdir()

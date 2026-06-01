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
from langflow.services.telemetry_writer.service import (
    _FAILURE_ESCALATION_THRESHOLD,
    TelemetryWriterService,
    _write_owner_file,
)
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
            "telemetry_writer_size_strategy": "count",
            "telemetry_writer_batch_size_bytes": 262_144,
            "telemetry_writer_max_queue_bytes": 209_715_200,
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


def test_count_strategy_ignores_byte_caps(writer_with_engine) -> None:
    """Default 'count' strategy must not track or cap bytes — preserves legacy semantics."""
    writer, _ = writer_with_engine
    writer.settings_service.settings.telemetry_writer_size_strategy = "count"
    writer.settings_service.settings.telemetry_writer_max_queue_bytes = 1  # tiny — would trip on bytes
    for i in range(5):
        writer.enqueue_transaction({"big": "x" * 1000, "i": i})
    assert len(writer._tx_buffer) == 5
    assert writer.dropped_transactions == 0
    # Byte tracking is disabled under 'count'.
    assert writer._tx_bytes == 0
    assert len(writer._tx_sizes) == 0


def test_bytes_strategy_drops_oldest_when_byte_cap_exceeded(writer_with_engine) -> None:
    """'bytes' strategy bounds memory regardless of row count."""
    writer, _ = writer_with_engine
    writer.settings_service.settings.telemetry_writer_size_strategy = "bytes"
    writer.settings_service.settings.telemetry_writer_max_queue = 10_000  # high — must not be the trigger
    writer.settings_service.settings.telemetry_writer_max_queue_bytes = 200
    # {"payload": "x"*100, "i": N} encodes to 123 bytes. Two of them (246) bust
    # the 200B cap, so on each subsequent enqueue the oldest is dropped first.
    for i in range(3):
        writer.enqueue_transaction({"payload": "x" * 100, "i": i})
    assert writer._tx_bytes == 123
    assert len(writer._tx_buffer) == 1
    assert writer.dropped_transactions == 2
    assert writer.dropped_transactions_bytes == 246


def test_either_strategy_trips_on_first_threshold(writer_with_engine) -> None:
    """'either' fires whichever cap (rows or bytes) is breached first."""
    writer, _ = writer_with_engine
    writer.settings_service.settings.telemetry_writer_size_strategy = "either"
    writer.settings_service.settings.telemetry_writer_max_queue = 3
    writer.settings_service.settings.telemetry_writer_max_queue_bytes = 10_000_000
    for i in range(5):
        writer.enqueue_transaction({"i": i})
    # Row cap trips first.
    assert len(writer._tx_buffer) == 3
    assert writer.dropped_transactions == 2


def test_drain_batch_respects_byte_budget(writer_with_engine) -> None:
    """Writer flush must split batches by bytes when strategy uses bytes."""
    writer, _ = writer_with_engine
    writer.settings_service.settings.telemetry_writer_size_strategy = "bytes"
    for i in range(10):
        writer.enqueue_transaction({"payload": "x" * 100, "i": i})
    # Each row encodes to 123 bytes. With a 250B budget the loop pops 3 rows
    # (123, 246, 369) and breaks on the third when batch_bytes >= max_bytes.
    batch = writer._drain_batch("transactions", max_n=10, max_bytes=250)
    assert len(batch) == 3
    assert len(writer._tx_buffer) == 7
    assert len(writer._tx_sizes) == 7
    assert writer._tx_bytes == 7 * 123


def test_drain_batch_always_emits_one_row_even_when_oversized(writer_with_engine) -> None:
    """A single row larger than the byte budget must still make progress."""
    writer, _ = writer_with_engine
    writer.settings_service.settings.telemetry_writer_size_strategy = "bytes"
    writer.enqueue_transaction({"big": "x" * 10_000})
    batch = writer._drain_batch("transactions", max_n=200, max_bytes=10)
    assert len(batch) == 1


def test_return_batch_to_buffer_restores_sizes(writer_with_engine) -> None:
    """Cancel/retry path must put rows AND their sizes back so accounting stays consistent."""
    writer, _ = writer_with_engine
    writer.settings_service.settings.telemetry_writer_size_strategy = "either"
    writer.enqueue_transaction({"a": 1})
    writer.enqueue_transaction({"b": 2})
    bytes_before = writer._tx_bytes
    batch = writer._drain_batch("transactions", max_n=2, max_bytes=10_000)
    assert writer._tx_bytes == 0
    writer._return_batch_to_buffer("transactions", batch)
    assert writer._tx_bytes == bytes_before
    assert len(writer._tx_sizes) == len(writer._tx_buffer) == 2


def test_bytes_strategy_round_trip_through_spill_and_restore(tmp_path: Path) -> None:
    """Spill must reset size tracking; restore must rebuild it via _enqueue."""
    own_dir = tmp_path / "pid"
    own_dir.mkdir()
    writer = _build_writer({"telemetry_writer_size_strategy": "either"})
    writer._started = True
    writer.enqueue_transaction({"flow": "a", "i": 1})
    writer.enqueue_transaction({"flow": "b", "i": 2})
    original_bytes = writer._tx_bytes
    assert original_bytes > 0
    assert len(writer._tx_sizes) == 2

    writer._spill_to_disk(own_dir, kind="transactions", buffer=writer._tx_buffer)
    # Spill drained the buffer and must zero size tracking.
    assert writer._tx_bytes == 0
    assert len(writer._tx_sizes) == 0
    assert not writer._tx_buffer

    # Restore into a fresh writer with the same strategy.
    restored = _build_writer({"telemetry_writer_size_strategy": "either"})
    restored._started = True
    restored._restore_from_disk(own_dir, kind="transactions", buffer=restored._tx_buffer)
    assert len(restored._tx_buffer) == 2
    assert len(restored._tx_sizes) == 2
    # Bytes must match the pre-spill total — restore re-encodes via _enqueue.
    assert restored._tx_bytes == original_bytes


def test_bytes_strategy_round_trip_through_adoption(tmp_path: Path) -> None:
    """Adopting an orphan outbox under 'bytes' strategy must populate size deques."""
    dead_pid = _find_dead_pid()
    dead_dir = tmp_path / str(dead_pid)
    dead_dir.mkdir()
    _write_owner_file(dead_dir)
    spill_writer = _build_writer({"telemetry_writer_size_strategy": "either"})
    spill_writer._started = True
    spill_writer.enqueue_transaction({"orphan": True, "i": 1})
    spill_writer.enqueue_transaction({"orphan": True, "i": 2})
    spilled_bytes = spill_writer._tx_bytes
    spill_writer._spill_to_disk(dead_dir, kind="transactions", buffer=spill_writer._tx_buffer)

    adopter = _build_writer({"telemetry_writer_size_strategy": "either"})
    adopter._adopt_orphan_outboxes(tmp_path, own_pid=1)
    assert len(adopter._tx_buffer) == 2
    assert len(adopter._tx_sizes) == 2
    assert adopter._tx_bytes == spilled_bytes


async def test_sweeper_calls_heartbeat_and_prune(tmp_path: Path) -> None:
    """One sweeper tick must touch our owner file and prune stale foreign dirs."""
    import json as _json
    import os as _os
    import time as _time

    own_dir = tmp_path / "1234"
    own_dir.mkdir()
    _write_owner_file(own_dir)
    owner_file = own_dir / "owner.json"
    aged = _time.time() - 7200
    _os.utime(owner_file, (aged, aged))
    own_before = owner_file.stat().st_mtime

    foreign_dir = tmp_path / "9999"
    foreign_dir.mkdir()
    (foreign_dir / "owner.json").write_text(
        _json.dumps({"host": "dead-foreign-pod", "boot": "x", "pid": 9999, "started_at": 0})
    )
    _os.utime(foreign_dir / "owner.json", (aged, aged))

    writer = _build_writer(
        {
            "telemetry_writer_outbox_dir": str(tmp_path),
            "telemetry_writer_orphan_max_age_s": 3600.0,
            # Skip the real retention pass — it needs a DB session.
            "telemetry_writer_cleanup_interval_s": 0.01,
        }
    )
    writer._own_outbox_dir = own_dir
    writer._shutdown_event = asyncio.Event()
    # Bypass _run_retention_pass by clearing the session_maker; the sweeper
    # catches the exception path either way, but None makes it a no-op.
    writer._session_maker = None

    async def _stop_after_one_tick() -> None:
        await asyncio.sleep(0.1)
        writer._shutdown_event.set()

    stopper = asyncio.create_task(_stop_after_one_tick())
    await writer._run_sweeper()
    await stopper

    assert owner_file.stat().st_mtime > own_before
    assert not foreign_dir.exists()


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


async def test_spill_restore_round_trip_writes_realistic_payload_to_db(writer_with_engine, tmp_path: Path) -> None:
    """Realistic payloads (UUID, datetime) survive JSON spill/restore and INSERT.

    Guards against the SQLite outbox's ``json.dumps(default=str)`` encoding
    breaking SQLAlchemy core inserts on the UUID/datetime columns of
    ``transaction`` / ``vertex_build`` once a row has been spilled to disk.
    """
    writer, engine = writer_with_engine
    flow_id = uuid4()
    writer._tx_buffer.append(_make_transaction_row(flow_id))
    writer._vb_buffer.append(_make_vertex_build_row(flow_id))

    own_dir = tmp_path / "pid"
    own_dir.mkdir()
    writer._spill_to_disk(own_dir, kind="transactions", buffer=writer._tx_buffer)
    writer._spill_to_disk(own_dir, kind="vertex_builds", buffer=writer._vb_buffer)
    writer._restore_from_disk(own_dir, kind="transactions", buffer=writer._tx_buffer)
    writer._restore_from_disk(own_dir, kind="vertex_builds", buffer=writer._vb_buffer)

    tx_batch = list(writer._tx_buffer)
    vb_batch = list(writer._vb_buffer)
    writer._tx_buffer.clear()
    writer._vb_buffer.clear()
    await writer._flush(tx_batch, vb_batch)

    async with AsyncSession(engine) as session:
        tx_count = await session.scalar(select(func.count()).select_from(TransactionTable))
        vb_count = await session.scalar(select(func.count()).select_from(VertexBuildTable))
    assert tx_count == 1
    assert vb_count == 1


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
    _write_owner_file(dead_dir)
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


def test_adopt_orphan_outboxes_skips_unknown_host(tmp_path: Path) -> None:
    """Cross-host or pre-reboot orphan dirs must not be adopted.

    Guards against PID reuse on container restart pulling in a stranger's
    spill data — the spill on disk is only adopted when the owner file's
    host + boot identity matches the current host.
    """
    import json as _json

    dead_pid = _find_dead_pid()
    dead_dir = tmp_path / str(dead_pid)
    dead_dir.mkdir()
    # Stamp a mismatched owner file.
    (dead_dir / "owner.json").write_text(
        _json.dumps({"host": "some-other-host", "boot": "unrelated-boot", "pid": dead_pid, "started_at": 0})
    )
    spill_writer = _build_writer()
    spill_writer._tx_buffer.extend([{"orphan": True}])
    spill_writer._spill_to_disk(dead_dir, kind="transactions", buffer=spill_writer._tx_buffer)

    own_writer = _build_writer()
    own_writer._adopt_orphan_outboxes(tmp_path, own_pid=1)
    assert list(own_writer._tx_buffer) == []
    # The orphan directory is left in place so a forensic operator can inspect it.
    assert dead_dir.exists()


def test_adopt_orphan_outboxes_skips_when_owner_missing(tmp_path: Path) -> None:
    """Pre-owner-file directories from older runs must not be silently adopted."""
    dead_pid = _find_dead_pid()
    dead_dir = tmp_path / str(dead_pid)
    dead_dir.mkdir()
    # No owner.json on purpose.
    spill_writer = _build_writer()
    spill_writer._tx_buffer.extend([{"orphan": True}])
    spill_writer._spill_to_disk(dead_dir, kind="transactions", buffer=spill_writer._tx_buffer)

    own_writer = _build_writer()
    own_writer._adopt_orphan_outboxes(tmp_path, own_pid=1)
    assert list(own_writer._tx_buffer) == []


def test_adopt_orphan_outboxes_honors_max_queue(tmp_path: Path) -> None:
    """A pathologically large orphan spill must not OOM the current worker.

    Regression for the case where ``_restore_from_disk`` and
    ``_adopt_orphan_outboxes`` appended directly to the deque, bypassing the
    queue cap.
    """
    dead_pid = _find_dead_pid()
    dead_dir = tmp_path / str(dead_pid)
    dead_dir.mkdir()
    _write_owner_file(dead_dir)
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


def test_prune_stale_foreign_outboxes_deletes_aged_cross_host_dirs(tmp_path: Path) -> None:
    """Cross-host orphan dirs older than max_age must be deleted from a shared volume."""
    import json as _json
    import os as _os
    import time as _time

    foreign_dir = tmp_path / "9999"
    foreign_dir.mkdir()
    owner_file = foreign_dir / "owner.json"
    owner_file.write_text(
        _json.dumps({"host": "some-other-host", "boot": "unrelated-boot", "pid": 9999, "started_at": 0})
    )
    # Backdate the owner file beyond the prune threshold.
    aged = _time.time() - 7200  # 2h ago, default max_age is 1h
    _os.utime(owner_file, (aged, aged))

    writer = _build_writer({"telemetry_writer_orphan_max_age_s": 3600.0})
    writer._prune_stale_foreign_outboxes(tmp_path)
    assert not foreign_dir.exists()


def test_prune_stale_foreign_outboxes_preserves_fresh_cross_host_dirs(tmp_path: Path) -> None:
    """A live foreign pod's outbox must not be deleted while it's actively heartbeating."""
    import json as _json

    foreign_dir = tmp_path / "1234"
    foreign_dir.mkdir()
    (foreign_dir / "owner.json").write_text(
        _json.dumps({"host": "live-foreign-pod", "boot": "unrelated-boot", "pid": 1234, "started_at": 0})
    )
    # Owner file mtime is "now" — pod is actively heartbeating.

    writer = _build_writer({"telemetry_writer_orphan_max_age_s": 3600.0})
    writer._prune_stale_foreign_outboxes(tmp_path)
    assert foreign_dir.exists()


def test_prune_stale_foreign_outboxes_leaves_same_host_dirs_alone(tmp_path: Path) -> None:
    """Same-host orphans are the adoption path's job, not the pruner's — even when aged."""
    import os as _os
    import time as _time

    own_dir = tmp_path / "5555"
    own_dir.mkdir()
    _write_owner_file(own_dir)
    owner_file = own_dir / "owner.json"
    aged = _time.time() - 7200
    _os.utime(owner_file, (aged, aged))

    writer = _build_writer({"telemetry_writer_orphan_max_age_s": 3600.0})
    writer._prune_stale_foreign_outboxes(tmp_path)
    assert own_dir.exists()


def test_heartbeat_owner_file_refreshes_mtime(tmp_path: Path) -> None:
    """The heartbeat must bump the owner file's mtime so foreign hosts can age us out."""
    import os as _os
    import time as _time

    own_dir = tmp_path / "1"
    own_dir.mkdir()
    _write_owner_file(own_dir)
    owner_file = own_dir / "owner.json"
    aged = _time.time() - 7200
    _os.utime(owner_file, (aged, aged))
    before = owner_file.stat().st_mtime

    writer = _build_writer()
    writer._own_outbox_dir = own_dir
    writer._heartbeat_owner_file()
    after = owner_file.stat().st_mtime
    assert after > before


def test_spill_caps_at_max_queue(tmp_path: Path) -> None:
    """A backlogged buffer at shutdown must not spill unbounded rows to disk.

    Older rows beyond ``telemetry_writer_max_queue`` are dropped (matching
    the producer-side overflow policy) and the drop counter is incremented.
    """
    own_dir = tmp_path / "pid"
    own_dir.mkdir()
    writer = _build_writer({"telemetry_writer_max_queue": 20})
    writer._tx_buffer.extend([{"i": i} for i in range(100)])
    writer._spill_to_disk(own_dir, kind="transactions", buffer=writer._tx_buffer)

    assert writer.dropped_transactions == 80
    # Round-trip what hit disk: only the newest 20 rows survive.
    restore = _build_writer({"telemetry_writer_max_queue": 1000})
    restore._restore_from_disk(own_dir, kind="transactions", buffer=restore._tx_buffer)
    assert [r["i"] for r in restore._tx_buffer] == list(range(80, 100))


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

    # Clean up the outbox directory tree.
    shutil.rmtree(outbox, ignore_errors=True)
    # Also clean up our potential tempfile fallback if used.
    fallback = Path(tempfile.gettempdir()) / "langflow_telemetry_outbox"
    if fallback.exists() and fallback.is_dir() and not any(fallback.iterdir()):
        fallback.rmdir()


async def test_retention_sweep_caps_vertex_builds_per_vertex(writer_with_engine) -> None:
    """Per-vertex cap must prune the oldest builds for a single vertex."""
    writer, engine = writer_with_engine
    writer.settings_service.settings.max_vertex_builds_per_vertex = 3
    writer.settings_service.settings.max_vertex_builds_to_keep = 10_000
    flow_id = uuid4()
    # Insert 8 builds for the same vertex — only 3 should survive.
    vb_batch = [_make_vertex_build_row(flow_id, vertex_id="v1") for _ in range(8)]
    await writer._flush([], vb_batch)
    await writer._run_retention_pass()

    async with AsyncSession(engine) as session:
        count = await session.scalar(select(func.count()).select_from(VertexBuildTable))
    assert count == 3


def test_either_strategy_trips_on_bytes_first(writer_with_engine) -> None:
    """'either' strategy must enforce the byte cap when it trips before the row cap."""
    writer, _ = writer_with_engine
    writer.settings_service.settings.telemetry_writer_size_strategy = "either"
    writer.settings_service.settings.telemetry_writer_max_queue = 10_000  # high — must not trigger
    writer.settings_service.settings.telemetry_writer_max_queue_bytes = 200
    # Each row encodes to ~123 bytes; two rows (246B) exceed the 200B cap.
    for i in range(3):
        writer.enqueue_transaction({"payload": "x" * 100, "i": i})
    # Byte cap trips first — same drop semantics as the bytes-only strategy.
    assert writer.dropped_transactions >= 1
    assert writer._tx_bytes <= 200


async def test_writer_retries_on_batch_failure(writer_with_engine) -> None:
    """Failed flush must increment failed_batches, return rows to buffer, then succeed on retry."""
    writer, engine = writer_with_engine
    writer.settings_service.settings.telemetry_writer_batch_size = 100
    writer.settings_service.settings.telemetry_writer_flush_interval_s = 0.01
    flow_id = uuid4()
    for _ in range(5):
        writer.enqueue_transaction(_make_transaction_row(flow_id))

    fail_count = 0

    real_flush = writer._flush.__func__

    async def _fail_twice(self, tx_batch, vb_batch):
        nonlocal fail_count
        if fail_count < 2:
            fail_count += 1
            msg = "injected failure"
            raise RuntimeError(msg)
        return await real_flush(self, tx_batch, vb_batch)

    import types

    writer._flush = types.MethodType(_fail_twice, writer)

    task = asyncio.create_task(writer._run_writer())
    # The two injected failures each return the batch to the buffer and back off
    # via _wait_or_shutdown. Setting the shutdown event short-circuits those
    # backoffs so the writer reaches its successful retry and drains — the
    # shutdown, not wall-clock waiting, is what lands the rows.
    writer._shutdown_event.set()
    await asyncio.wait_for(task, timeout=5)

    assert writer.failed_batches == 2
    assert writer.flushed_rows == 5
    async with AsyncSession(engine) as session:
        final = await session.scalar(select(func.count()).select_from(TransactionTable))
    assert final == 5


async def test_writer_escalates_after_threshold_failures(writer_with_engine) -> None:
    """Consecutive failures past the threshold must keep retrying (exercises the `>=` branch, not `==`)."""
    import types

    writer, engine = writer_with_engine
    writer.settings_service.settings.telemetry_writer_batch_size = 100
    writer.settings_service.settings.telemetry_writer_flush_interval_s = 0.01
    flow_id = uuid4()
    for _ in range(5):
        writer.enqueue_transaction(_make_transaction_row(flow_id))

    # Fail one more than the threshold so the escalation branch runs at counts
    # both equal to and greater than the threshold — exactly what `>=` covers
    # and `==` would not.
    fail_target = _FAILURE_ESCALATION_THRESHOLD + 1
    fail_count = 0
    real_flush = writer._flush.__func__

    async def _fail_n_times(self, tx_batch, vb_batch):
        nonlocal fail_count
        if fail_count < fail_target:
            fail_count += 1
            msg = "injected failure"
            raise RuntimeError(msg)
        return await real_flush(self, tx_batch, vb_batch)

    writer._flush = types.MethodType(_fail_n_times, writer)

    task = asyncio.create_task(writer._run_writer())
    # Short-circuit every backoff so the failures (and the final success) run fast.
    writer._shutdown_event.set()
    await asyncio.wait_for(task, timeout=5)

    # Every injected failure was counted (driving consecutive_failures past the
    # threshold), then the buffer drained on the success.
    assert writer.failed_batches == fail_target
    assert writer.flushed_rows == 5
    async with AsyncSession(engine) as session:
        final = await session.scalar(select(func.count()).select_from(TransactionTable))
    assert final == 5


async def test_teardown_cancelled_still_spills_buffer(writer_with_engine, tmp_path: Path) -> None:
    """If teardown() is itself cancelled, the in-memory buffer must still spill to disk."""
    writer, _ = writer_with_engine
    own_dir = tmp_path / "pid"
    own_dir.mkdir()
    writer._own_outbox_dir = own_dir
    # Long drain so teardown blocks in the writer-drain await while we cancel it.
    writer.settings_service.settings.telemetry_writer_shutdown_drain_s = 30.0

    for i in range(3):
        writer.enqueue_transaction({"cancelled_spill": i})
    assert len(writer._tx_buffer) == 3

    # A writer task that never finishes on its own, so teardown stays parked in
    # the drain await until we cancel it.
    async def _never() -> None:
        await asyncio.Event().wait()

    writer._writer_task = asyncio.create_task(_never())

    teardown_task = asyncio.create_task(writer.teardown())
    await asyncio.sleep(0.05)  # let teardown reach the drain await
    teardown_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await teardown_task

    # The cancellation must not have dropped the buffer: a fresh reader pointed
    # at the same outbox sees the spilled rows.
    reader = _build_writer()
    reader._restore_from_disk(own_dir, kind="transactions", buffer=reader._tx_buffer)
    assert [row["cancelled_spill"] for row in reader._tx_buffer] == [0, 1, 2]

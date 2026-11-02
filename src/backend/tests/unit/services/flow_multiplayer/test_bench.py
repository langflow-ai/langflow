"""The ops bench: gc_startup through a reset, and the journal that outlives a killed process. No database, no server."""

from __future__ import annotations

from langflow.services.flow_multiplayer import bench


def test_reset_keeps_gc_startup(monkeypatch):
    startup = {"kind": "gc_startup", "freeze_count": 0, "gen2_objects": 1}
    monkeypatch.setattr(bench, "_gc_startup", startup)
    monkeypatch.setattr(bench, "_records", [startup, {"kind": "req"}, {"kind": "gc", "gen": 2}])
    bench.reset()
    assert bench._records == [startup]
    bench.reset()
    assert bench._records == [startup]


def _journal_on(monkeypatch, tmp_path):
    from langflow.services.flow_multiplayer import config

    monkeypatch.setenv(config.BENCH_ENV, "1")
    monkeypatch.setenv(config.BENCH_DIR_ENV, str(tmp_path))
    config.reset_for_tests()
    monkeypatch.setattr(bench, "_records", [])
    monkeypatch.setattr(bench, "_gc_startup", None)
    _new_process(monkeypatch)


def _new_process(monkeypatch):
    """Forget the journal file, as a new process does (same pid, as in a restarted container)."""
    monkeypatch.setattr(bench, "_journal_fd", None)
    monkeypatch.setattr(bench, "_journal_path", None)
    monkeypatch.setattr(bench, "_journal_pid", None)


def _close_journal():
    import os

    if bench._journal_fd is not None:
        os.close(bench._journal_fd)


def _exported():
    import orjson

    return [orjson.loads(line) for line in bench.export_jsonl().splitlines()]


def test_journal_keeps_records_of_a_killed_process(monkeypatch, tmp_path):
    """Records flushed by a process that is gone come back in the next process's export."""
    import time

    from langflow.services.flow_multiplayer import config

    _journal_on(monkeypatch, tmp_path)
    try:
        bench.reset()
        t = time.time()
        bench._records.extend({"kind": "req", "pid": 1, "t": t + i} for i in range(5))
        assert bench.flush() == 5
        assert bench._records == []  # flushed records leave memory
        assert bench.flush() == 0
        bench._records.append({"kind": "req", "pid": 1, "t": t + 9})  # not flushed: lost with the process
        # SIGKILL: the memory is gone; a new process starts with the same directory and pid.
        _close_journal()
        monkeypatch.setattr(bench, "_records", [])
        _new_process(monkeypatch)
        bench._records.append({"kind": "req", "pid": 1, "t": t + 20})
        records = _exported()
        assert sorted(r["t"] for r in records) == [t + i for i in range(5)] + [t + 20]
        assert len({r["boot"] for r in records}) == 2
        assert len(list(tmp_path.glob("bench-*.jsonl"))) == 2
    finally:
        _close_journal()
        config.reset_for_tests()


def test_journal_makes_no_file_for_a_process_without_records(monkeypatch, tmp_path):
    """The server's parent process imports the bench and flushes at exit, but never records."""
    from langflow.services.flow_multiplayer import config

    _journal_on(monkeypatch, tmp_path)
    try:
        assert bench.flush() == 0
        assert bench._journal_fd is None
        assert list(tmp_path.iterdir()) == []
    finally:
        config.reset_for_tests()


def test_journal_export_leaves_out_records_before_the_reset_and_a_torn_line(monkeypatch, tmp_path):
    import time

    from langflow.services.flow_multiplayer import config

    _journal_on(monkeypatch, tmp_path)
    try:
        startup = {"kind": "gc_startup", "pid": 1, "t": time.time() - 100}
        monkeypatch.setattr(bench, "_gc_startup", startup)
        bench._records.extend([startup, {"kind": "req", "pid": 1, "t": time.time() - 50}])
        bench.flush()
        bench.reset()  # gc_startup goes to the journal a second time; the export has it once
        bench.event("checkpoint", flow="f", revision=100)
        bench.flush()
        with open(bench._journal_path, "ab") as f:  # noqa: PTH123
            f.write(b'{"kind":"req","pid":1,"t":')  # killed while writing this line
        records = _exported()
        assert [r["kind"] for r in records] == ["gc_startup", "checkpoint"]
        assert records[1]["revision"] == 100
    finally:
        _close_journal()
        config.reset_for_tests()


def test_journal_flusher_thread_writes_while_the_loop_is_blocked(monkeypatch, tmp_path):
    """A saturated event loop does not stop the journal: the flusher is a thread."""
    import time

    from langflow.services.flow_multiplayer import config

    _journal_on(monkeypatch, tmp_path)
    monkeypatch.setattr(bench, "SAMPLE_INTERVAL", 0.01)
    monkeypatch.setattr(bench, "_flusher", None)
    try:
        bench._ensure_flusher()
        bench._records.extend({"kind": "lag", "pid": 1, "t": time.time()} for _ in range(3))
        deadline = time.monotonic() + 5
        while bench._records and time.monotonic() < deadline:
            time.sleep(0.01)  # the caller holds the loop; only the thread can flush
        assert bench._records == []
        assert len((tmp_path / bench._journal_path.rsplit("/", 1)[1]).read_bytes().splitlines()) == 3
    finally:
        bench.stop_flusher()
        _close_journal()
        config.reset_for_tests()


def test_journal_export_without_a_server(monkeypatch, tmp_path):
    """``python -m ...bench DIR`` prints the export of a directory (a pod whose server does not answer)."""
    import subprocess
    import sys
    import time

    from langflow.services.flow_multiplayer import config

    _journal_on(monkeypatch, tmp_path)
    try:
        bench.reset()
        bench._records.append({"kind": "req", "pid": 1, "t": time.time() + 1})
        bench.flush()
        expected = bench.export_jsonl()
        out = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "langflow.services.flow_multiplayer.bench", str(tmp_path)],
            check=True,
            capture_output=True,
        ).stdout
        assert out == expected
        assert out.count(b'"kind":"req"') == 1
    finally:
        _close_journal()
        config.reset_for_tests()


def test_without_journal_export_is_memory_only(monkeypatch, tmp_path):
    from langflow.services.flow_multiplayer import config

    monkeypatch.delenv(config.BENCH_DIR_ENV, raising=False)
    config.reset_for_tests()
    monkeypatch.setattr(bench, "_records", [{"kind": "req", "pid": 1, "t": 1.0}])
    monkeypatch.setattr(bench, "_journal_fd", None)
    assert bench.flush() == 0
    bench._ensure_flusher()
    assert bench._flusher is None or not bench._flusher.is_alive()
    assert bench.export_jsonl() == b'{"kind":"req","pid":1,"t":1.0}\n'
    assert list(tmp_path.iterdir()) == []


async def test_pool_probe_records_the_wait_for_a_connection(tmp_path):
    """A request that waits for the pool's only connection records the wait in ``pool_wait_part``."""
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import AsyncAdaptedQueuePool

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'pool.db'}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=10,
    )
    pool = engine.sync_engine.pool
    bench._wrap_pool_checkout(pool)
    bench._wrap_pool_checkout(pool)  # once only
    holding = asyncio.Event()

    async def holder() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            holding.set()
            await asyncio.sleep(0.3)

    async def waiter() -> dict:
        rec: dict = {}
        token = bench._current.set(rec)
        try:
            await holding.wait()
            assert bench._pool_fields(pool)["pool_out"] == 1
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            bench._current.reset(token)
        return rec

    try:
        _, rec = await asyncio.gather(holder(), waiter())
    finally:
        await engine.dispose()
    assert rec["pool_get_n"] == 1
    assert 200 < rec["pool_wait_part"] < 2000
    assert rec["pool_wait_max_part"] == rec["pool_wait_part"]
    assert bench._pool_waiting == 0

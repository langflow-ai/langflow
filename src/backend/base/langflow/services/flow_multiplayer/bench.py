"""Server-side measurement of multiplayer requests, on only when ``LANGFLOW_OPS_BENCH=1``.

Per request (``kind: "req"``): endpoint, status, total time and the time of
each step in milliseconds:

- ``pre``: before the route handler starts (middleware, the current-user dependency);
- ``auth``: the flow's permission check (one read of the flow row without ``data``);
- ``lock``: waiting for the flow's advisory lock;
- ``head``: reading the head revision (and the retry lookup);
- ``load``: reading ``Flow.data`` and building the graph (engine);
- ``catchup``: replaying log rows (engine), with ``catchup_n`` operations;
- ``stage``: applying the batch (engine);
- ``append``: inserting the log rows;
- ``ser``: serializing the graph (engine); ``flow_write``: writing ``Flow.data``;
- ``commit``; ``keep``: keeping the staged batch (engine);
- ``close``: leaving the database session (the connection goes back to the pool);
- ``out``: from the handler's answer to the response start leaving the inner middleware;
  ``send``: from the response start to its last body byte.

Engine calls add ``eng_<call>`` (wall, measured around the call itself, inside
any lock) and ``eng_<call>_cpu`` (CPU time of the thread that ran it). Fields
named ``eng_*``, ``*_db``, ``*_part`` and ``*_n`` are parts of a step, not steps; every other
numeric field except ``total`` is one step, and steps do not overlap, so
``total`` minus the steps is the time no step accounts for. ``parse`` is reading
and parsing the body, ``respond`` building the answer.

Checkpoints (``kind: "checkpoint"``) record start, end, duration and revision,
with the engine CPU of their serialization and hash. Background tasks
(checkpoints, maintenance, the sampler) run in an empty context, so they never
add to a request's record.
A sampler records process CPU time, the event loop thread's CPU time
(``loop_cpu_s``) and RSS every second (``kind: "sample"``),
with the database pool's use: ``pool_out`` (connections checked out),
``pool_overflow``, ``pool_waiting`` (callers waiting for a connection or
connecting) and ``tasks`` (asyncio tasks).

Database pool: every request record gets ``pool_wait_part`` (time spent
getting connections from the pool, the wait for a free one included),
``pool_wait_max_part`` (the longest single wait) and ``pool_get_n``. The health
endpoints (``/health``, ``/healthz``) get request records too.
Each sample also has ``threads``: the CPU seconds of each thread of the process
(``/proc``), ``loop_tid`` (the thread that runs the event loop), ``gc_collections``
(collections so far per generation), ``gc_count`` and ``blocks`` (allocated memory
blocks). With ``LANGFLOW_OPS_BENCH_GC_OBJECTS=1``, a gen-2 ``gc`` record has
``gen2_objects``: the tracked objects the full collection traverses, counted just
before it starts (outside ``dur``, but on the loop thread, and long for many
objects, so it stays off in measured runs).
Compactions (``kind: "compaction"``) record start, end and the time of every
phase, with ``lock_held`` from the advisory lock granted to the commit's end
and ``checkpoints_delete``, the unlocked transaction after it.

Engine calls of at least ``ECALL_RECORD_MS`` (wall) also add one ``kind: "ecall"``
record with ``name``, ``t`` (start), ``end``, ``dur``, ``cpu`` (the running thread's
CPU), ``loop`` (ran on the event loop's thread) and ``bg`` (outside a request, such as
a checkpoint), so a request can be matched with the engine calls it overlapped.

Three probes look for stalls. They start with the first measured
request (the first flow request, before the benchmark resets the records):

- ``kind: "gc"``: every gen-2 collection and any collection over
  ``GC_RECORD_MS``, with its start ``t``, ``gen``, ``dur`` and ``collected``;
  one ``kind: "gc_startup"`` record has the frozen object count and the
  objects in generation 2 when the probe started. A reset keeps it.
- ``kind: "lag"``: the loop woke more than ``LAG_RECORD_MS`` late from a
  ``LAG_INTERVAL`` sleep; ``t`` is when the stall began (about), ``lag`` its length.
- ``kind: "gil"``: a plain thread woke more than ``GIL_RECORD_MS`` late from a
  ``GIL_INTERVAL`` sleep. A thread that runs bytecode gives the GIL up within the
  switch interval (5 ms), so a late wake-up means one call held the GIL that long
  (a C call, or a garbage collection); a loop stall without one is the loop's own work.

``LANGFLOW_OPS_BENCH_LAG_MS``, ``LANGFLOW_OPS_BENCH_GIL_MS`` and
``LANGFLOW_OPS_BENCH_ECALL_MS`` change the three thresholds.

Everything stays in memory until the bench export endpoint reads it; a reset
deletes every record except ``gc_startup``.

Journal (``LANGFLOW_OPS_BENCH_DIR``): the records also go to a JSONL file in
that directory, one file per process (``bench-<pid>-<start ns>.jsonl``). A
flusher thread appends the new records every ``SAMPLE_INTERVAL`` and drops
them from memory; the process also flushes at exit and before an export. The
thread runs when the event loop is saturated, so a process killed with SIGKILL
loses only the records of its last interval, plus the requests still in
flight (a request record is written when its response ends). A reset writes
its time to ``reset-at`` in the directory. The export then reads every journal
file in the directory, also those of processes that are gone (a container
restarted in the same pod keeps an ``emptyDir``), and returns the records with
``t`` at or after the reset (``gc_startup`` once per file), each with ``boot``
(its file's name), because a restarted container can get the same pid.
``python -m langflow.services.flow_multiplayer.bench DIR`` prints the same
export without a running server.
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import contextvars
import gc
import glob
import os
import sys
import threading
import time
from contextvars import ContextVar
from typing import Any, Self

import orjson

from langflow.services.flow_multiplayer import config

_current: ContextVar[dict[str, Any] | None] = ContextVar("flow_ops_bench_record", default=None)
_records: list[dict[str, Any]] = []
_sampler: asyncio.Task | None = None
_lag_probe: asyncio.Task | None = None
_journal_fd: int | None = None
_journal_path: str | None = None
_journal_pid: int | None = None
_journal_lock = threading.Lock()  # flush and reset: the flusher thread drops flushed records
_flusher: threading.Thread | None = None
_flusher_stop = threading.Event()
RESET_FILE = "reset-at"
_pool_waiting = 0  # callers inside the pool's checkout
_PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
SAMPLE_INTERVAL = 1.0
LAG_INTERVAL = 0.01
LAG_RECORD_MS = float(os.environ.get("LANGFLOW_OPS_BENCH_LAG_MS") or 50.0)
GIL_INTERVAL = 0.005
GIL_RECORD_MS = float(os.environ.get("LANGFLOW_OPS_BENCH_GIL_MS") or 20.0)
ECALL_RECORD_MS = float(os.environ.get("LANGFLOW_OPS_BENCH_ECALL_MS") or 5.0)
GC_RECORD_MS = 20.0
GC_COUNT_OBJECTS = (os.environ.get("LANGFLOW_OPS_BENCH_GC_OBJECTS") or "").strip().lower() in ("1", "true", "yes")
_loop_thread: int | None = None
_gil_probe: threading.Thread | None = None
PATH_PREFIXES = ("/api/v2/flows", "/api/v1/flows", "/health")


def record() -> dict[str, Any] | None:
    """The current request's record, or None when measurement is off."""
    return _current.get()


def add(name: str, value: float) -> None:
    rec = _current.get()
    if rec is not None:
        rec[name] = rec.get(name, 0) + value


def mark_handler() -> None:
    """Record when the route handler starts: ``pre`` is the time spent before it (middleware, auth dependency)."""
    rec = _current.get()
    if rec is not None:
        rec["pre"] = (time.perf_counter() - rec["_t0"]) * 1000


def put(name: str, value: Any) -> None:
    rec = _current.get()
    if rec is not None:
        rec[name] = value


class _Timer:
    __slots__ = ("name", "rec", "t0")

    def __init__(self, rec: dict[str, Any], name: str) -> None:
        self.rec = rec
        self.name = name

    def __enter__(self) -> Self:
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *_exc: object) -> None:
        now = time.perf_counter()
        self.rec[self.name] = self.rec.get(self.name, 0) + (now - self.t0) * 1000
        if self.name == "respond":
            self.rec["_t_done"] = now


_NULL = contextlib.nullcontext()


def timed(name: str) -> Any:
    """Add the time of the ``with`` block to the current record's ``name`` (milliseconds)."""
    rec = _current.get()
    if rec is None:
        return _NULL
    return _Timer(rec, name)


def engine_call(name: str, function: Any, *args: Any, **kwargs: Any) -> Any:
    """Run one engine call, adding its wall time and its thread's CPU time to the current record.

    A call of at least ``ECALL_RECORD_MS`` also adds an ``ecall`` record, in a request or not.
    """
    rec = _current.get()
    if rec is None and not config.bench_enabled():
        return function(*args, **kwargs)
    t0, c0, w0 = time.perf_counter(), time.thread_time(), time.time()
    try:
        return function(*args, **kwargs)
    finally:
        c1, t1 = time.thread_time(), time.perf_counter()
        dur, cpu = (t1 - t0) * 1000, (c1 - c0) * 1000
        if rec is not None:
            key = f"eng_{name}"
            rec[key] = rec.get(key, 0) + dur
            rec[key + "_cpu"] = rec.get(key + "_cpu", 0) + cpu
        if dur >= ECALL_RECORD_MS:
            _records.append(
                {
                    "kind": "ecall",
                    "pid": os.getpid(),
                    "name": name,
                    "t": w0,
                    "end": w0 + dur / 1000,
                    "dur": dur,
                    "cpu": cpu,
                    "loop": threading.get_ident() == _loop_thread,
                    "bg": rec is None,
                }
            )


def engine_call_cpu(function: Any, *args: Any, **kwargs: Any) -> tuple[Any, float]:
    """Run one engine call; return its result and its thread's CPU time in milliseconds."""
    c0 = time.thread_time()
    result = function(*args, **kwargs)
    return result, (time.thread_time() - c0) * 1000


def spawn(coro: Any) -> asyncio.Task:
    """A background task in an empty context: it never adds to the request record that started it."""
    return asyncio.get_running_loop().create_task(coro, context=contextvars.Context())


def event(kind: str, **fields: Any) -> None:
    if config.bench_enabled():
        _records.append({"kind": kind, "pid": os.getpid(), "t": time.time(), **fields})


def _journal() -> int | None:
    """The journal's file descriptor, opened on first use in each process; None when the journal is off."""
    global _journal_fd, _journal_path, _journal_pid  # noqa: PLW0603
    if _journal_fd is not None and _journal_pid == os.getpid():
        return _journal_fd
    directory = config.bench_dir()
    if directory is None:
        return None
    os.makedirs(directory, exist_ok=True)  # noqa: PTH103
    _journal_pid = os.getpid()
    _journal_path = os.path.join(directory, f"bench-{_journal_pid}-{time.time_ns()}.jsonl")  # noqa: PTH118
    _journal_fd = os.open(_journal_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    return _journal_fd


def flush() -> int:
    """Append the records in memory to the journal and drop them from memory; returns how many.

    No-op without a journal. On a write error the records stay in memory for the next flush.
    """
    with _journal_lock:
        count = len(_records)
        if not count:
            return 0  # no file for a process that never records (the server's parent process)
        fd = _journal()
        if fd is None:
            return 0
        data = b"".join(orjson.dumps(rec, option=orjson.OPT_APPEND_NEWLINE) for rec in _records[:count])
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        # Other threads only append (the gc probe, the loop), so the first ``count`` are the flushed ones.
        del _records[:count]
        return count


def _flush_loop(stop: threading.Event) -> None:
    while not stop.wait(SAMPLE_INTERVAL):
        # A full or missing journal never stops the flusher; the records stay in memory.
        with contextlib.suppress(OSError):
            flush()


def _ensure_flusher() -> None:
    global _flusher  # noqa: PLW0603
    if config.bench_dir() is None or (_flusher is not None and _flusher.is_alive()):
        return
    _flusher_stop.clear()
    _flusher = threading.Thread(target=_flush_loop, args=(_flusher_stop,), name="flow-ops-bench-journal", daemon=True)
    _flusher.start()


def stop_flusher() -> None:
    """Stop the flusher thread and wait for it (tests)."""
    global _flusher  # noqa: PLW0603
    _flusher_stop.set()
    if _flusher is not None:
        _flusher.join()
    _flusher = None


def _reset_at(directory: str) -> float:
    try:
        with open(os.path.join(directory, RESET_FILE), "rb") as f:  # noqa: PTH118, PTH123
            return float(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0.0


def _write_reset_at(directory: str, when: float) -> None:
    os.makedirs(directory, exist_ok=True)  # noqa: PTH103
    path = os.path.join(directory, RESET_FILE)  # noqa: PTH118
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:  # noqa: PTH123
        f.write(repr(when))
    os.replace(tmp, path)  # noqa: PTH105


def _journal_records(directory: str) -> list[bytes]:
    """Every journal record at or after the last reset, from every process's file, with ``boot``."""
    since = _reset_at(directory)
    lines: list[bytes] = []
    startups: set[tuple[str, int | None]] = set()
    for path in sorted(glob.glob(os.path.join(directory, "bench-*.jsonl"))):  # noqa: PTH118, PTH207
        boot = os.path.basename(path)[: -len(".jsonl")]  # noqa: PTH119
        with open(path, "rb") as f:  # noqa: PTH123
            data = f.read()
        for line in data.split(b"\n"):
            if not line:
                continue
            try:
                rec = orjson.loads(line)
            except orjson.JSONDecodeError:
                continue  # the last line of a process killed while writing it
            if rec.get("kind") == "gc_startup":
                key = (boot, rec.get("pid"))
                if key in startups:
                    continue
                startups.add(key)
            elif (rec.get("t") or 0) < since:
                continue
            rec["boot"] = boot
            lines.append(orjson.dumps(rec, option=orjson.OPT_APPEND_NEWLINE))
    return lines


def _rss_bytes() -> int:
    try:
        with open("/proc/self/statm", "rb") as f:  # noqa: PTH123
            return int(f.read().split()[1]) * _PAGE
    except OSError:
        return 0


_TICKS = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def _thread_cpu() -> dict[str, float]:
    """CPU seconds (user + system) of each thread of this process, by native thread id."""
    out: dict[str, float] = {}
    try:
        tids = os.listdir("/proc/self/task")  # noqa: PTH208
    except OSError:
        return out
    for tid in tids:
        try:
            with open(f"/proc/self/task/{tid}/stat", "rb") as f:  # noqa: PTH123
                fields = f.read().rsplit(b")", 1)[1].split()
        except OSError:
            continue
        # Fields after the command: state is index 0, utime 11, stime 12.
        out[tid] = (int(fields[11]) + int(fields[12])) / _TICKS
    return out


def _wrap_pool_checkout(pool: Any) -> None:
    """Time every checkout of ``pool`` (``_do_get``: a free connection, a new one, or the wait for one)."""
    if getattr(pool, "_ops_bench_probe", False):
        return
    inner = pool._do_get  # noqa: SLF001 -- no public event marks the start of a checkout

    def _do_get() -> Any:
        global _pool_waiting  # noqa: PLW0603
        _pool_waiting += 1
        t0 = time.perf_counter()
        try:
            return inner()
        finally:
            _pool_waiting -= 1
            waited = (time.perf_counter() - t0) * 1000
            # SQLAlchemy's async greenlet runs in the caller's context: this is the request's record.
            rec = _current.get()
            if rec is not None:
                rec["pool_wait_part"] = rec.get("pool_wait_part", 0) + waited
                rec["pool_get_n"] = rec.get("pool_get_n", 0) + 1
                rec["pool_wait_max_part"] = max(rec.get("pool_wait_max_part", 0), waited)

    pool._do_get = _do_get  # noqa: SLF001
    pool._ops_bench_probe = True  # noqa: SLF001


def _db_pool() -> Any | None:
    """The database pool, its checkout timed; None before the database service exists."""
    try:
        from langflow.services.deps import get_db_service

        pool = get_db_service().engine.sync_engine.pool
    except Exception:  # noqa: BLE001 -- measurement never breaks the server
        return None
    _wrap_pool_checkout(pool)
    return pool


def _pool_fields(pool: Any | None) -> dict[str, Any]:
    if pool is None:
        return {}
    fields: dict[str, Any] = {"pool_waiting": _pool_waiting}
    for name, method in (("pool_out", "checkedout"), ("pool_overflow", "overflow")):
        with contextlib.suppress(Exception):
            fields[name] = getattr(pool, method)()
    return fields


async def _sample_loop() -> None:
    loop_tid = threading.get_native_id()
    while True:
        _records.append(
            {
                "kind": "sample",
                "pid": os.getpid(),
                "t": time.time(),
                "cpu_s": time.process_time(),
                # The event loop thread's own CPU: near 1 s per second when the loop is saturated.
                "loop_cpu_s": time.thread_time(),
                "rss": _rss_bytes(),
                "threads": _thread_cpu(),
                "loop_tid": loop_tid,
                "gc_collections": [g["collections"] for g in gc.get_stats()],
                "gc_count": list(gc.get_count()),
                "blocks": sys.getallocatedblocks(),
                "tasks": len(asyncio.all_tasks()),
                **_pool_fields(_db_pool()),
            }
        )
        await asyncio.sleep(SAMPLE_INTERVAL)


async def _lag_loop() -> None:
    while True:
        t0 = time.perf_counter()
        await asyncio.sleep(LAG_INTERVAL)
        lag = (time.perf_counter() - t0 - LAG_INTERVAL) * 1000
        if lag > LAG_RECORD_MS:
            now = time.time()
            _records.append({"kind": "lag", "pid": os.getpid(), "t": now - lag / 1000, "end": now, "lag": lag})


def _gil_loop() -> None:
    while True:
        t0 = time.perf_counter()
        time.sleep(GIL_INTERVAL)
        lag = (time.perf_counter() - t0 - GIL_INTERVAL) * 1000
        if lag > GIL_RECORD_MS:
            now = time.time()
            _records.append({"kind": "gil", "pid": os.getpid(), "t": now - lag / 1000, "end": now, "lag": lag})


class _GcProbe:
    """A ``gc.callbacks`` entry: two clock reads per collection, a record only for gen 2 or a slow one."""

    __slots__ = ("gen2_objects", "started", "wall")

    def __init__(self) -> None:
        self.started: float | None = None
        self.wall = 0.0
        self.gen2_objects: int | None = None

    def __call__(self, phase: str, info: dict[str, Any]) -> None:
        if phase == "start":
            # What a full collection traverses: the tracked objects of generation 2 (frozen ones are not).
            # Off by default: listing every generation-2 object lengthens each gen-2 pause, on the loop thread.
            count = GC_COUNT_OBJECTS and info.get("generation") == 2  # noqa: PLR2004
            self.gen2_objects = len(gc.get_objects(generation=2)) if count else None
            self.started = time.perf_counter()
            self.wall = time.time()
            return
        if self.started is None:
            return
        dur = (time.perf_counter() - self.started) * 1000
        self.started = None
        generation = info.get("generation")
        if generation == 2 or dur > GC_RECORD_MS:  # noqa: PLR2004
            _records.append(
                {
                    "kind": "gc",
                    "pid": os.getpid(),
                    "t": self.wall,
                    "gen": generation,
                    "dur": dur,
                    "collected": info.get("collected"),
                    "uncollectable": info.get("uncollectable"),
                    "gen2_objects": self.gen2_objects,
                }
            )


_gc_probe: _GcProbe | None = None
_gc_startup: dict[str, Any] | None = None


def _install_gc_probe() -> None:
    global _gc_probe, _gc_startup  # noqa: PLW0603
    if _gc_probe is not None:
        return
    _gc_probe = _GcProbe()
    _gc_startup = {
        "kind": "gc_startup",
        "pid": os.getpid(),
        "t": time.time(),
        "freeze_count": gc.get_freeze_count(),
        "gen2_objects": len(gc.get_objects(generation=2)),
        "count": list(gc.get_count()),
        "threshold": list(gc.get_threshold()),
    }
    _records.append(_gc_startup)
    gc.callbacks.append(_gc_probe)


def _ensure_sampler() -> None:
    global _sampler, _lag_probe, _loop_thread, _gil_probe  # noqa: PLW0603
    if _sampler is None or _sampler.done():
        _loop_thread = threading.get_ident()
        _install_gc_probe()
        _db_pool()
        _sampler = spawn(_sample_loop())
    if _gil_probe is None:
        _gil_probe = threading.Thread(target=_gil_loop, name="ops-bench-gil-probe", daemon=True)
        _gil_probe.start()
    if _lag_probe is None or _lag_probe.done():
        _lag_probe = spawn(_lag_loop())
    _ensure_flusher()


def export_jsonl() -> bytes:
    directory = config.bench_dir()
    if directory is not None:
        flush()
        return b"".join(_journal_records(directory))
    return b"".join(orjson.dumps(rec, option=orjson.OPT_APPEND_NEWLINE) for rec in list(_records))


def reset() -> None:
    """Delete every record but ``gc_startup``, which is taken once per process.

    With a journal, the reset time goes to ``reset-at`` so the export leaves out older records,
    also those of other processes' files.
    """
    with _journal_lock:
        _records.clear()
        if _gc_startup is not None:
            _records.append(_gc_startup)
        directory = config.bench_dir()
        if directory is not None:
            _write_reset_at(directory, time.time())


def _flush_at_exit() -> None:
    with contextlib.suppress(OSError):
        flush()


atexit.register(_flush_at_exit)


class BenchMiddleware:
    """Pure ASGI middleware: one record per flow request, written when the response ends."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(PATH_PREFIXES):
            await self.app(scope, receive, send)
            return
        _ensure_sampler()
        rec: dict[str, Any] = {
            "kind": "req",
            "pid": os.getpid(),
            "t": time.time(),
            "method": scope["method"],
            "path": scope["path"],
            "mode": config.write_mode(),
            "engine": config.engine().name,
        }
        t0 = time.perf_counter()
        rec["_t0"] = t0
        token = _current.set(rec)

        async def send_wrapper(message: dict) -> None:
            now = time.perf_counter()
            if message["type"] == "http.response.start":
                rec["status"] = message["status"]
                rec["_t_start"] = now
                if "_t_done" in rec:
                    # From the handler's answer to the response leaving the inner middleware.
                    rec["out"] = (now - rec["_t_done"]) * 1000
            elif message["type"] == "http.response.body" and not message.get("more_body"):
                rec["total"] = (now - t0) * 1000
                if "_t_start" in rec:
                    rec["send"] = (now - rec["_t_start"]) * 1000
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            rec.setdefault("total", (time.perf_counter() - t0) * 1000)
            for key in ("_t0", "_t_done", "_t_start"):
                rec.pop(key, None)
            _current.reset(token)
            _records.append(rec)


if __name__ == "__main__":
    # The export of a journal directory, without a server: a pod whose server does not answer.
    sys.stdout.buffer.write(b"".join(_journal_records(sys.argv[1])))

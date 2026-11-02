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
A sampler records process CPU time and RSS every second (``kind: "sample"``),
with ``threads``: the CPU seconds of each thread of the process (``/proc``),
and ``loop_tid``, the thread that runs the event loop; ``gc_collections`` (collections so
far per generation), ``gc_count`` and ``blocks`` (allocated memory blocks). A gen-2 ``gc``
record has ``gen2_objects``: the tracked objects the full collection traverses, counted
just before it starts (outside ``dur``).
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
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import gc
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
_PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
SAMPLE_INTERVAL = 1.0
LAG_INTERVAL = 0.01
LAG_RECORD_MS = float(os.environ.get("LANGFLOW_OPS_BENCH_LAG_MS") or 50.0)
GIL_INTERVAL = 0.005
GIL_RECORD_MS = float(os.environ.get("LANGFLOW_OPS_BENCH_GIL_MS") or 20.0)
ECALL_RECORD_MS = float(os.environ.get("LANGFLOW_OPS_BENCH_ECALL_MS") or 5.0)
GC_RECORD_MS = 20.0
_loop_thread: int | None = None
_gil_probe: threading.Thread | None = None
PATH_PREFIXES = ("/api/v2/flows", "/api/v1/flows")


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
        _records.append({"kind": kind, "pid": os.getpid(), **fields})


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


async def _sample_loop() -> None:
    loop_tid = threading.get_native_id()
    while True:
        _records.append(
            {
                "kind": "sample",
                "pid": os.getpid(),
                "t": time.time(),
                "cpu_s": time.process_time(),
                "rss": _rss_bytes(),
                "threads": _thread_cpu(),
                "loop_tid": loop_tid,
                "gc_collections": [g["collections"] for g in gc.get_stats()],
                "gc_count": list(gc.get_count()),
                "blocks": sys.getallocatedblocks(),
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
            self.gen2_objects = len(gc.get_objects(generation=2)) if info.get("generation") == 2 else None  # noqa: PLR2004
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
        _sampler = spawn(_sample_loop())
    if _gil_probe is None:
        _gil_probe = threading.Thread(target=_gil_loop, name="ops-bench-gil-probe", daemon=True)
        _gil_probe.start()
    if _lag_probe is None or _lag_probe.done():
        _lag_probe = spawn(_lag_loop())


def export_jsonl() -> bytes:
    return b"".join(orjson.dumps(rec, option=orjson.OPT_APPEND_NEWLINE) for rec in list(_records))


def reset() -> None:
    """Delete every record but ``gc_startup``, which is taken once per process."""
    _records.clear()
    if _gc_startup is not None:
        _records.append(_gc_startup)


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

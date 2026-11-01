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
A sampler records process CPU time and RSS every second (``kind: "sample"``).
Everything stays in memory until the bench export endpoint reads it.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import os
import time
from contextvars import ContextVar
from typing import Any, Self

import orjson

from langflow.services.flow_multiplayer import config

_current: ContextVar[dict[str, Any] | None] = ContextVar("flow_ops_bench_record", default=None)
_records: list[dict[str, Any]] = []
_sampler: asyncio.Task | None = None
_PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
SAMPLE_INTERVAL = 1.0
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
    """Run one engine call, adding its wall time and its thread's CPU time to the current record."""
    rec = _current.get()
    if rec is None:
        return function(*args, **kwargs)
    t0, c0 = time.perf_counter(), time.thread_time()
    try:
        return function(*args, **kwargs)
    finally:
        c1, t1 = time.thread_time(), time.perf_counter()
        key = f"eng_{name}"
        rec[key] = rec.get(key, 0) + (t1 - t0) * 1000
        rec[key + "_cpu"] = rec.get(key + "_cpu", 0) + (c1 - c0) * 1000


def engine_call_cpu(function: Any, *args: Any, **kwargs: Any) -> tuple[Any, float]:
    """Run one engine call; return its result and its thread's CPU time in milliseconds."""
    c0 = time.thread_time()
    result = function(*args, **kwargs)
    return result, (time.thread_time() - c0) * 1000


def spawn(coro: Any) -> asyncio.Task:
    """A background task in an empty context: it never adds to the request record that started it."""
    return asyncio.get_running_loop().create_task(coro, context=contextvars.Context())


class MeasuredEngine:
    """The engine object, with every function call measured as ``eng_<function>`` (legacy write path)."""

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._engine, name)
        if not callable(value) or isinstance(value, type):
            return value

        def measured(*args: Any, **kwargs: Any) -> Any:
            return engine_call(name, value, *args, **kwargs)

        return measured


def event(kind: str, **fields: Any) -> None:
    if config.bench_enabled():
        _records.append({"kind": kind, "pid": os.getpid(), **fields})


def _rss_bytes() -> int:
    try:
        with open("/proc/self/statm", "rb") as f:  # noqa: PTH123
            return int(f.read().split()[1]) * _PAGE
    except OSError:
        return 0


async def _sample_loop() -> None:
    while True:
        _records.append(
            {
                "kind": "sample",
                "pid": os.getpid(),
                "t": time.time(),
                "cpu_s": time.process_time(),
                "rss": _rss_bytes(),
            }
        )
        await asyncio.sleep(SAMPLE_INTERVAL)


def _ensure_sampler() -> None:
    global _sampler  # noqa: PLW0603
    if _sampler is None or _sampler.done():
        _sampler = spawn(_sample_loop())


def export_jsonl() -> bytes:
    return b"".join(orjson.dumps(rec, option=orjson.OPT_APPEND_NEWLINE) for rec in list(_records))


def reset() -> None:
    _records.clear()


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

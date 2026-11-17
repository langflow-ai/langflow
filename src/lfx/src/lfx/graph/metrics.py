"""Opt-in bounded statistics for calls on one executable graph."""

from __future__ import annotations

import asyncio
import math
import threading
import time

_clock = time.perf_counter


class ExecutionMetrics:
    """A completed-call report, scoped to a single asyncio loop and thread."""

    def __init__(self, graph):
        self._loop = asyncio.get_running_loop()
        self._thread = threading.get_ident()
        self._names = {v.id: str(v.display_name) if v.display_name is not None else v.id for v in graph.vertices}
        self._flow_id = str(graph.flow_id) if graph.flow_id is not None else None
        self._flow_name = str(graph.flow_name) if graph.flow_name is not None else None
        self._start = _clock()
        if not math.isfinite(self._start):
            msg = "Metrics clock must be finite"
            raise ValueError(msg)
        self._elapsed = 0.0
        self._active = True
        self._inflight = 0
        self._incomplete = False
        self._nodes = {}

    def _owned(self):
        if threading.get_ident() != self._thread:
            return False
        try:
            return asyncio.get_running_loop() is self._loop
        except RuntimeError:
            return False

    def _begin(self, vertex_id):
        if not self._active or not self._owned() or vertex_id not in self._names:
            return None
        try:
            start = _clock()
            if not math.isfinite(start):
                self._incomplete = True
                return None
        except Exception:  # noqa: BLE001 - diagnostics must not change execution
            self._incomplete = True
            return None
        self._inflight += 1
        return start

    def _record(self, vertex_id, start, outcome):
        if start is None or not self._active or not self._owned():
            return
        duration = float(_clock() - start)
        if not math.isfinite(duration) or duration < 0:
            self._incomplete = True
            return
        row = self._nodes.setdefault(
            vertex_id,
            {
                "display_name": self._names[vertex_id],
                "call_count": 0,
                "returned_count": 0,
                "raised_count": 0,
                "cancelled_count": 0,
                "total_duration_seconds": 0.0,
                "min_duration_seconds": duration,
                "max_duration_seconds": duration,
                "last_duration_seconds": duration,
            },
        )
        total = row["total_duration_seconds"] + duration
        if not math.isfinite(total):
            self._incomplete = True
            return
        row["call_count"] += 1
        row[outcome + "_count"] += 1
        row["total_duration_seconds"] = total
        row["min_duration_seconds"] = min(row["min_duration_seconds"], duration)
        row["max_duration_seconds"] = max(row["max_duration_seconds"], duration)
        row["last_duration_seconds"] = duration

    def _finish(self, vertex_id, start, outcome, *, primary=False):
        if start is None or not self._active or not self._owned():
            return
        self._inflight -= 1
        try:
            self._record(vertex_id, start, outcome)
        except BaseException as exc:
            self._incomplete = True
            if not isinstance(exc, Exception) and not primary:
                raise

    def _update_elapsed(self):
        try:
            elapsed = _clock() - self._start
            if math.isfinite(elapsed) and elapsed >= self._elapsed:
                self._elapsed = elapsed
            else:
                self._incomplete = True
        except Exception:  # noqa: BLE001 - diagnostics only
            self._incomplete = True

    def snapshot(self):
        """Return detached finalized calls; active snapshots require the owner loop."""
        if self._active:
            if not self._owned():
                msg = "Active metrics snapshots require the owner loop and thread"
                raise RuntimeError(msg)
            self._update_elapsed()
        return {
            "flow_id": self._flow_id,
            "flow_name": self._flow_name,
            "elapsed_seconds": float(self._elapsed),
            "incomplete": self._incomplete,
            "nodes": {key: dict(self._nodes[key]) for key in sorted(self._nodes)},
        }

    def _close(self, *, primary=False):
        if not self._owned():
            if not primary:
                msg = "Metrics scope exit requires the owner loop and thread"
                raise RuntimeError(msg)
            return
        try:
            self._update_elapsed()
        except BaseException:
            if not primary:
                raise
        finally:
            self._incomplete |= self._inflight != 0
            self._active = False


class _ExecutionMetricsScope:
    def __init__(self, graph):
        self._graph = graph
        self._recorder = None

    def __enter__(self):
        if self._recorder is not None or getattr(self._graph, "_execution_metrics", None) is not None:
            msg = "A metrics scope is already active on this graph"
            raise RuntimeError(msg)
        recorder = ExecutionMetrics(self._graph)
        self._graph._execution_metrics = recorder  # noqa: SLF001
        self._recorder = recorder
        return recorder

    def __exit__(self, exc_type, _exc, _traceback):
        recorder = self._recorder
        if recorder is None or not recorder._active:  # noqa: SLF001
            return False
        # Reject before consuming the scope: the owner must still be able to
        # close it after a foreign exit attempt, even with a primary exception.
        if not recorder._owned():  # noqa: SLF001
            if exc_type is None:
                msg = "Metrics scope exit requires the owner loop and thread"
                raise RuntimeError(msg)
            return False
        try:
            recorder._close(primary=exc_type is not None)  # noqa: SLF001
        finally:
            self._graph._execution_metrics = None  # noqa: SLF001
        return False


def collect_execution_metrics(graph):
    """Collect only calls executed on this graph in the current asyncio loop.

    Drain or cancel and await tasks before exit. Late completions are dropped.
    Copies, resumed graphs and synchronous worker-thread execution are not covered.
    """
    return _ExecutionMetricsScope(graph)

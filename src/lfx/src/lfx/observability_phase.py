"""Fixed-label application phase histograms; no spans, stream wrapper or content labels."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from enum import Enum
from functools import lru_cache
from time import perf_counter, thread_time

from lfx.observability import APPLICATION_METER_NAME, EVENT_LOOP_LAG_BUCKETS_SECONDS

try:
    from opentelemetry import metrics
except ImportError:
    metrics = None


# Seconds, including sub-millisecond setup/final-callback regions. Preserve the
# application's established loop-lag boundaries and extend the wall upper tail.
WALL_BUCKETS_SECONDS = (0.0001, 0.0005, *EVENT_LOOP_LAG_BUCKETS_SECONDS, 30.0, 60.0)
THREAD_CPU_BUCKETS_SECONDS = (
    0.00001,
    0.00005,
    0.0001,
    0.00025,
    0.0005,
    *EVENT_LOOP_LAG_BUCKETS_SECONDS,
)
OUTCOMES = frozenset({"ok", "error", "cancelled", "interrupted"})


class Phase(str, Enum):
    PREPARE = "prepare"
    MODEL_CLIENT = "model_client"
    AGENT_SETUP = "agent_setup"
    AGENT_EXECUTE = "agent_execute"
    FINAL_SEND = "final_send"
    OUTPUT_PERSIST = "output_persist"


@lru_cache(maxsize=1)
def _instruments():
    if metrics is None:
        return None
    meter = metrics.get_meter(APPLICATION_METER_NAME)
    return (
        meter.create_histogram(
            "langflow.agent.phase.duration",
            unit="s",
            description="Wall time of application phases; phases may overlap or be nested.",
            explicit_bucket_boundaries_advisory=list(WALL_BUCKETS_SECONDS),
        ),
        meter.create_histogram(
            "langflow.agent.phase.thread_cpu",
            unit="s",
            description="Calling-thread CPU inside uninterrupted synchronous phase regions only.",
            explicit_bucket_boundaries_advisory=list(THREAD_CPU_BUCKETS_SECONDS),
        ),
    )


def _record(phase, outcome, wall, cpu):
    # Validation and SDK failures cannot replace the operation's return/error.
    try:
        if not isinstance(phase, Phase) or not isinstance(outcome, str) or outcome not in OUTCOMES:
            return
        instruments = _instruments()
        if instruments is None:
            return
        attributes = {"phase": phase.value, "outcome": outcome}
        instruments[0].record(wall, attributes)
        if cpu is not None:
            instruments[1].record(cpu, attributes)
    except Exception:  # noqa: BLE001 - telemetry must preserve execution behavior
        return


class PhaseResult:
    """Stack-local closed outcome controls for handled errors and approval pauses."""

    def __init__(self):
        self._outcome = "ok"

    @property
    def outcome(self):
        return self._outcome

    def error(self):
        self._outcome = "error"

    def cancelled(self):
        self._outcome = "cancelled"

    def interrupted(self):
        self._outcome = "interrupted"


@contextmanager
def measure_phase(phase: Phase):
    """Wall time including awaits; never attributes calling-thread/request CPU."""
    if not isinstance(phase, Phase):
        msg = "phase must be a fixed Phase value"
        raise TypeError(msg)
    start = perf_counter()
    result = PhaseResult()
    try:
        yield result
    except asyncio.CancelledError:
        result.cancelled()
        raise
    except BaseException:
        result.error()
        raise
    finally:
        _record(phase, result.outcome, perf_counter() - start, None)


@contextmanager
def measure_sync_phase(phase: Phase):
    """Pure synchronous default setup only; no await, reentrant loop or custom I/O."""
    if phase is not Phase.AGENT_SETUP:
        msg = "thread CPU is restricted to uninterrupted agent setup"
        raise ValueError(msg)
    start, cpu_start = perf_counter(), thread_time()
    result = PhaseResult()
    try:
        yield result
    except asyncio.CancelledError:
        result.cancelled()
        raise
    except BaseException:
        result.error()
        raise
    finally:
        _record(phase, result.outcome, perf_counter() - start, thread_time() - cpu_start)

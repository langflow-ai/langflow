"""Process-wide configuration of multiplayer writes: the engine object, the write mode and the cache size."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Literal

WRITE_MODE_ENV = "LANGFLOW_FLOW_WRITE_MODE"
CACHE_MAX_FLOWS_ENV = "LANGFLOW_FLOW_CACHE_MAX_FLOWS"
BENCH_ENV = "LANGFLOW_OPS_BENCH"
BENCH_DIR_ENV = "LANGFLOW_OPS_BENCH_DIR"
WRITERS_PER_FLOW_ENV = "LANGFLOW_FLOW_WRITERS_PER_FLOW"

WriteMode = Literal["nocache", "cache", "wal"]
WRITE_MODES: tuple[str, ...] = ("nocache", "cache", "wal")
DEFAULT_CACHE_MAX_FLOWS = 16
DEFAULT_WRITERS_PER_FLOW = 1

# Engine calls on inputs above these sizes run in a worker thread; smaller ones run inline.
# The same rule applies to both engines.
LARGE_OPS_BYTES = 256 * 1024
LARGE_OPS_COUNT = 64


@lru_cache(maxsize=1)
def engine() -> Any:
    """The process's flow engine object (``LANGFLOW_FLOW_ENGINE``: python or rust)."""
    from lfx.services.flow_operations.engine import get_engine

    return get_engine()


@lru_cache(maxsize=1)
def write_mode() -> WriteMode:
    mode = (os.environ.get(WRITE_MODE_ENV) or "nocache").strip().lower()
    if mode not in WRITE_MODES:
        msg = f"{WRITE_MODE_ENV} must be one of {', '.join(WRITE_MODES)}, not {mode!r}"
        raise ValueError(msg)
    return mode  # type: ignore[return-value]


@lru_cache(maxsize=1)
def cache_max_flows() -> int:
    raw = os.environ.get(CACHE_MAX_FLOWS_ENV)
    value = int(raw) if raw else DEFAULT_CACHE_MAX_FLOWS
    if value < 1:
        msg = f"{CACHE_MAX_FLOWS_ENV} must be at least 1"
        raise ValueError(msg)
    return value


@lru_cache(maxsize=1)
def writers_per_flow() -> int:
    """Writers of one flow that may hold a database connection at a time in this process (0: no limit).

    The others wait in the process, without a connection, so writers queued on one flow's lock
    cannot take the whole pool.
    """
    raw = os.environ.get(WRITERS_PER_FLOW_ENV)
    value = int(raw) if raw else DEFAULT_WRITERS_PER_FLOW
    if value < 0:
        msg = f"{WRITERS_PER_FLOW_ENV} must be 0 (no limit) or more"
        raise ValueError(msg)
    return value


def uses_cache() -> bool:
    return write_mode() in ("cache", "wal")


@lru_cache(maxsize=1)
def bench_enabled() -> bool:
    return os.environ.get(BENCH_ENV, "").strip().lower() in ("1", "true", "yes")


@lru_cache(maxsize=1)
def bench_dir() -> str | None:
    """Directory for the bench journal (``LANGFLOW_OPS_BENCH_DIR``), or None to keep records in memory only."""
    raw = (os.environ.get(BENCH_DIR_ENV) or "").strip()
    return raw or None


def checkpoint_cadence() -> int:
    from langflow.services.deps import get_settings_service

    return get_settings_service().settings.flow_revision_checkpoint_cadence


def compaction_step() -> int:
    """Operations past the retention window before compaction runs (default 10 checkpoint cadences)."""
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    return settings.flow_revision_compaction_step or 10 * settings.flow_revision_checkpoint_cadence


def reset_for_tests() -> None:
    """Forget the cached configuration, so a test can change the environment."""
    for function in (engine, write_mode, cache_max_flows, bench_enabled, bench_dir, writers_per_flow):
        function.cache_clear()

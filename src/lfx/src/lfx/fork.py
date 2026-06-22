"""Fork-safety helpers for pre-fork / pre-snapshot warm-up paths.

A process about to ``fork()`` (Gunicorn ``--preload``) or be snapshotted must not be
holding fork-hostile state: non-main threads (they vanish in the child, possibly mid-lock)
or live non-listening TCP connections (their file descriptors are shared into every child).
These helpers detect that state so a warm-up path can confirm it's safe to fork/snapshot
and dispose any fork-unsafe resources first.

Shared by Langflow's Gunicorn server (`pre_fork` hook) and lfx serve's prewarm.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

# Threads known to be safe to leave before a fork: they die in the child harmlessly and
# produce no side effects when their fd is inherited.
BENIGN_THREAD_PREFIXES: tuple[str, ...] = (
    "OTel",  # OpenTelemetry SDK (BatchSpanProcessor, etc.)
    "opentelemetry",  # alternate OTel naming
    "prometheus",  # Prometheus client background threads
    "loguru",  # loguru enqueue=True worker
    "asyncio",  # event-loop helper threads (Python internals)
    "ThreadPoolExecutor",  # stdlib executor — harmless in parent
    "concurrent.futures",  # same pool, different prefix
)


def is_benign_thread(thread: threading.Thread) -> bool:
    """Return True if *thread* is known-safe to leave running before a fork."""
    return any(thread.name.startswith(prefix) for prefix in BENIGN_THREAD_PREFIXES)


def find_ghost_threads() -> list[threading.Thread]:
    """Return alive non-main threads that are not on the benign allowlist."""
    main = threading.main_thread()
    return [t for t in threading.enumerate() if t.is_alive() and t is not main and not is_benign_thread(t)]


def find_ghost_connections() -> list[str]:
    """Return non-listening TCP connections as formatted strings.

    Returns ``[]`` when psutil is not installed. Any other failure (e.g. permission denied)
    propagates; use :func:`fork_safety_report` for best-effort behaviour that swallows it.
    """
    try:
        import psutil
    except ImportError:
        return []
    conns = psutil.Process().net_connections(kind="tcp")
    return [f"{c.laddr}->{c.raddr} ({c.status})" for c in conns if c.status != "LISTEN"]


@dataclass
class ForkSafetyReport:
    """Fork-hostile state found in the current process."""

    ghost_threads: list[str] = field(default_factory=list)
    ghost_connections: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.ghost_threads and not self.ghost_connections


def fork_safety_report() -> ForkSafetyReport:
    """Snapshot the current process's fork-hostile state (threads + TCP connections).

    Best-effort: if connection inspection fails it is reported as empty rather than raised.
    """
    try:
        connections = find_ghost_connections()
    except Exception:  # noqa: BLE001 - best-effort; a warm-up report must not crash the warm-up
        connections = []
    return ForkSafetyReport(
        ghost_threads=[t.name for t in find_ghost_threads()],
        ghost_connections=connections,
    )


@contextmanager
def fork_safe_teardown(*closers: Callable[[], object]) -> Iterator[None]:
    """Run a block, then ALWAYS invoke each closer — even on exception.

    Use this to dispose fork-unsafe resources (DB engines, cache sockets, clients) before a
    fork/snapshot. A closer that raises is logged and the remaining closers still run.
    """
    try:
        yield
    finally:
        for close in closers:
            try:
                close()
            except Exception:  # noqa: BLE001 - one closer must not block the others
                logger.exception("[fork] teardown closer failed")

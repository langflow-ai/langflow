"""Global in-memory store for RunPayload events emitted by log_package_run.

All RunPayload objects queued through TelemetryService.log_package_run are
appended here in addition to the normal Scarf telemetry queue.  Enterprise
code (and any other internal consumer) can import RUN_EVENT_STORE directly
and drain it at whatever cadence they need.

Thread / asyncio safety:
  - list.append() is atomic in CPython (GIL), safe for concurrent appends.
  - Callers draining the list should use pop_all() which swaps the underlying
    list atomically to avoid races between drain and append.
"""

from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.telemetry.schema import RunPayload

_lock = Lock()

# The global list that accumulates every RunPayload seen during this process
# lifetime.  Enterprise consumers read from this; the OSS telemetry pipeline
# is completely unaffected.
RUN_EVENT_STORE: list[RunPayload] = []


def append_run_event(payload: RunPayload) -> None:
    """Append a RunPayload to the global store.

    Called by TelemetryService.log_package_run before queueing to Scarf.
    """
    with _lock:
        RUN_EVENT_STORE.append(payload)


def pop_all() -> list[RunPayload]:
    """Atomically drain and return all accumulated RunPayload events.

    The store is reset to an empty list so subsequent appends start fresh.
    Callers (e.g. the UMS telemetry bridge) should call this on each flush
    cycle to avoid double-reporting.
    """
    with _lock:
        global RUN_EVENT_STORE
        events, RUN_EVENT_STORE = RUN_EVENT_STORE, []
    return events


def peek_all() -> list[RunPayload]:
    """Return a snapshot of all events without draining the store.

    Useful for read-only inspection (dashboards, debug endpoints).
    Does not affect subsequent pop_all() calls.
    """
    with _lock:
        return list(RUN_EVENT_STORE)

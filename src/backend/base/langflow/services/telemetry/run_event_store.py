"""In-process store of completed-run events for enterprise metering.

TelemetryService.log_package_run appends every RunPayload here before the
do-not-track gate: metering consumers must see every run even when outbound
telemetry is disabled. Nothing in OSS reads the store — enterprise builds
drain it periodically via pop_all() — and events never leave the process
unless such a consumer is installed. The store is bounded so a deployment
without a consumer holds at most _MAX_EVENTS payloads.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.telemetry.schema import RunPayload

_MAX_EVENTS = 10_000

_lock = threading.Lock()
_events: list[RunPayload] = []


def append_run_event(payload: RunPayload) -> None:
    """Append a run event, discarding the oldest events beyond the bound."""
    with _lock:
        _events.append(payload)
        if len(_events) > _MAX_EVENTS:
            del _events[: len(_events) - _MAX_EVENTS]


def pop_all() -> list[RunPayload]:
    """Atomically drain and return all pending events."""
    with _lock:
        drained = list(_events)
        _events.clear()
        return drained


def peek_all() -> list[RunPayload]:
    """Return a snapshot of pending events without draining."""
    with _lock:
        return list(_events)

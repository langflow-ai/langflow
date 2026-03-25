from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock

from langflow.services.base import Service


@dataclass(frozen=True)
class FlowEvent:
    type: str
    timestamp: float
    summary: str = ""


class FlowEventsService(Service):
    """In-memory event queue keyed by flow_id. Thread-safe. TTL-based cleanup."""

    name = "flow_events_service"

    TTL_SECONDS: float = 60.0
    SETTLE_TIMEOUT: float = 10.0

    def __init__(self) -> None:
        self._events: dict[str, list[FlowEvent]] = {}
        self._lock = Lock()

    def append(self, flow_id: str, event_type: str, summary: str = "") -> FlowEvent:
        event = FlowEvent(type=event_type, timestamp=time.time(), summary=summary)
        with self._lock:
            self._cleanup(flow_id)
            self._events.setdefault(flow_id, []).append(event)
        return event

    def get_since(self, flow_id: str, since: float) -> tuple[list[FlowEvent], bool]:
        """Return (events_after_since, settled).

        settled is True if:
        - No events exist for this flow, OR
        - A flow_settled event exists after `since`, OR
        - The most recent event is older than SETTLE_TIMEOUT seconds.
        """
        with self._lock:
            self._cleanup(flow_id)
            all_events = list(self._events.get(flow_id, []))

        after = [e for e in all_events if e.timestamp > since]

        if not after and not all_events:
            return [], True

        if any(e.type == "flow_settled" for e in after):
            return after, True

        last_event_age = time.time() - all_events[-1].timestamp
        settled = last_event_age >= self.SETTLE_TIMEOUT

        return after, settled

    def _cleanup(self, flow_id: str) -> None:
        cutoff = time.time() - self.TTL_SECONDS
        if flow_id in self._events:
            self._events[flow_id] = [e for e in self._events[flow_id] if e.timestamp > cutoff]
            if not self._events[flow_id]:
                del self._events[flow_id]

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock

from langflow.services.base import Service


@dataclass
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
        - A flow_settled event exists after `since`, OR
        - Events exist but the most recent one is older than SETTLE_TIMEOUT seconds.
        """
        with self._lock:
            self._cleanup(flow_id)
            all_events = self._events.get(flow_id, [])

        after = [e for e in all_events if e.timestamp > since]

        if not after and not all_events:
            return [], True

        has_settled_event = any(e.type == "flow_settled" for e in after)
        if has_settled_event:
            return after, True

        if all_events:
            last_event_age = time.time() - all_events[-1].timestamp
            settled = last_event_age >= self.SETTLE_TIMEOUT
        else:
            settled = True

        return after, settled

    def _cleanup(self, flow_id: str) -> None:
        cutoff = time.time() - self.TTL_SECONDS
        if flow_id in self._events:
            self._events[flow_id] = [e for e in self._events[flow_id] if e.timestamp > cutoff]
            if not self._events[flow_id]:
                del self._events[flow_id]

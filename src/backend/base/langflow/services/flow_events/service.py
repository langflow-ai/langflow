from __future__ import annotations

import json
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, get_args

from diskcache import Cache

from langflow.services.base import Service

FLOW_EVENT_TYPES = Literal[
    "component_added",
    "component_removed",
    "component_configured",
    "connection_added",
    "connection_removed",
    "flow_updated",
    "flow_settled",
]


@dataclass(frozen=True)
class FlowEvent:
    type: str
    timestamp: float
    summary: str = ""


class FlowEventsService(Service):
    """Disk-backed event queue keyed by flow_id.

    Uses diskcache for cross-worker visibility (multiple uvicorn/gunicorn workers
    share the same SQLite-backed cache directory). TTL-based cleanup is handled
    by diskcache's built-in expiry.

    Limitations:
    - Events are ephemeral: lost on disk cleanup or container restart.
      This is acceptable since events only drive transient UI state (banner, canvas lock).
    - Multiple browser tabs polling the same flow will each see events independently
      but may show slightly different banner/lock state due to independent polling cycles.
    """

    name = "flow_events_service"

    TTL_SECONDS: float = 60.0
    SETTLE_TIMEOUT: float = 10.0
    MAX_EVENTS_PER_FLOW: int = 1000

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "langflow_flow_events"
        self._cache = Cache(str(cache_dir))

    _VALID_EVENT_TYPES: frozenset[str] = frozenset(get_args(FLOW_EVENT_TYPES))

    def append(self, flow_id: str, event_type: str, summary: str = "") -> FlowEvent:
        if event_type not in self._VALID_EVENT_TYPES:
            msg = f"Invalid event type: {event_type!r}. Must be one of {sorted(self._VALID_EVENT_TYPES)}"
            raise ValueError(msg)
        event = FlowEvent(type=event_type, timestamp=time.time(), summary=summary)
        key = f"flow_events:{flow_id}"

        with self._cache.transact():
            raw = self._cache.get(key, default=None)
            events: list[dict] = json.loads(raw) if raw else []
            events.append(asdict(event))
            # Trim to max size
            if len(events) > self.MAX_EVENTS_PER_FLOW:
                events = events[-self.MAX_EVENTS_PER_FLOW :]
            self._cache.set(key, json.dumps(events), expire=self.TTL_SECONDS)

        return event

    def get_since(self, flow_id: str, since: float) -> tuple[list[FlowEvent], bool]:
        """Return (events_after_since, settled).

        settled is True if:
        - No events exist for this flow, OR
        - A flow_settled event exists after `since`, OR
        - The most recent event is older than SETTLE_TIMEOUT seconds.
        """
        key = f"flow_events:{flow_id}"
        raw = self._cache.get(key, default=None)
        all_events = [FlowEvent(**e) for e in json.loads(raw)] if raw else []

        after = [e for e in all_events if e.timestamp > since]

        if not after and not all_events:
            return [], True

        if any(e.type == "flow_settled" for e in after):
            return after, True

        last_event_age = time.time() - all_events[-1].timestamp
        settled = last_event_age >= self.SETTLE_TIMEOUT

        return after, settled

    async def teardown(self) -> None:
        self._cache.close()

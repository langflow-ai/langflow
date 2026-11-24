from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

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


_SCHEMA = """
CREATE TABLE IF NOT EXISTS flow_events (
    flow_id    TEXT NOT NULL,
    ts         REAL NOT NULL,
    type       TEXT NOT NULL,
    summary    TEXT NOT NULL DEFAULT '',
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_flow_events_flow_ts ON flow_events(flow_id, ts);
CREATE INDEX IF NOT EXISTS idx_flow_events_expires ON flow_events(expires_at);
"""


class FlowEventsService(Service):
    """SQLite-backed event queue keyed by flow_id.

    Uses Python's stdlib sqlite3 in WAL mode for cross-worker visibility (multiple
    uvicorn/gunicorn workers share the same on-disk database file). TTL-based
    cleanup is performed lazily on each write and read.

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

    _VALID_EVENT_TYPES: frozenset[str] = frozenset(get_args(FLOW_EVENT_TYPES))

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "langflow_flow_events"
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = cache_dir / "flow_events.sqlite"
        # isolation_level=None puts pysqlite in autocommit mode so we manage
        # transactions explicitly via BEGIN/COMMIT.
        self._conn = sqlite3.connect(
            str(self._db_path),
            isolation_level=None,
            check_same_thread=False,
            timeout=5.0,
        )
        # Serialize use of the single connection across asyncio tasks / FastAPI threads
        # in this worker. WAL handles cross-worker concurrency.
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.executescript(_SCHEMA)

    def append(self, flow_id: str, event_type: str, summary: str = "") -> FlowEvent:
        if event_type not in self._VALID_EVENT_TYPES:
            msg = f"Invalid event type: {event_type!r}. Must be one of {sorted(self._VALID_EVENT_TYPES)}"
            raise ValueError(msg)

        now = time.time()
        event = FlowEvent(type=event_type, timestamp=now, summary=summary)
        expires_at = now + self.TTL_SECONDS

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                # Opportunistic TTL cleanup across all flows.
                self._conn.execute("DELETE FROM flow_events WHERE expires_at < ?", (now,))
                self._conn.execute(
                    "INSERT INTO flow_events (flow_id, ts, type, summary, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (flow_id, now, event_type, summary, expires_at),
                )
                # Bound per-flow size: keep only the most recent MAX_EVENTS_PER_FLOW rows.
                # Order by (ts, rowid) so events appended in the same microsecond have a
                # stable, insertion-aware ordering when picking which rows to drop.
                self._conn.execute(
                    """
                    DELETE FROM flow_events
                    WHERE rowid IN (
                        SELECT rowid FROM flow_events
                        WHERE flow_id = ?
                        ORDER BY ts DESC, rowid DESC
                        LIMIT -1 OFFSET ?
                    )
                    """,
                    (flow_id, self.MAX_EVENTS_PER_FLOW),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

        return event

    def get_since(self, flow_id: str, since: float) -> tuple[list[FlowEvent], bool]:
        """Return (events_after_since, settled).

        settled is True if:
        - No events exist for this flow, OR
        - A flow_settled event exists after `since`, OR
        - The most recent event is older than SETTLE_TIMEOUT seconds.
        """
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT type, ts, summary
                FROM flow_events
                WHERE flow_id = ? AND expires_at >= ?
                ORDER BY ts ASC, rowid ASC
                """,
                (flow_id, now),
            ).fetchall()

        all_events = [FlowEvent(type=r[0], timestamp=r[1], summary=r[2]) for r in rows]
        after = [e for e in all_events if e.timestamp > since]

        if not after and not all_events:
            return [], True

        if any(e.type == "flow_settled" for e in after):
            return after, True

        last_event_age = time.time() - all_events[-1].timestamp
        settled = last_event_age >= self.SETTLE_TIMEOUT

        return after, settled

    async def teardown(self) -> None:
        with self._lock:
            self._conn.close()

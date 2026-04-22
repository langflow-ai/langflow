from __future__ import annotations

import sqlite3
import tempfile
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


class FlowEventsService(Service):
    """SQLite-backed event queue keyed by flow_id.

    Events are stored in a small SQLite database so multiple uvicorn/gunicorn
    workers can observe the same flow state without requiring an external cache.

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
    DB_FILENAME = "flow_events.sqlite3"

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "langflow_flow_events"
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._cache_dir / self.DB_FILENAME
        self._initialize_db()

    _VALID_EVENT_TYPES: frozenset[str] = frozenset(get_args(FLOW_EVENT_TYPES))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_db(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS flow_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flow_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    summary TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_flow_events_flow_timestamp
                ON flow_events(flow_id, timestamp, id)
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(flow_events)").fetchall()}
            if "expires_at" not in columns:
                connection.execute("ALTER TABLE flow_events ADD COLUMN expires_at REAL")
                connection.execute(
                    "UPDATE flow_events SET expires_at = timestamp + ? WHERE expires_at IS NULL",
                    (self.TTL_SECONDS,),
                )

    def _delete_expired_events(self, connection: sqlite3.Connection, *, now: float) -> None:
        connection.execute("DELETE FROM flow_events WHERE expires_at <= ?", (now,))

    def append(self, flow_id: str, event_type: str, summary: str = "") -> FlowEvent:
        if event_type not in self._VALID_EVENT_TYPES:
            msg = f"Invalid event type: {event_type!r}. Must be one of {sorted(self._VALID_EVENT_TYPES)}"
            raise ValueError(msg)
        event = FlowEvent(type=event_type, timestamp=time.time(), summary=summary)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._delete_expired_events(connection, now=event.timestamp)
            connection.execute(
                """
                INSERT INTO flow_events(flow_id, event_type, timestamp, expires_at, summary)
                VALUES (?, ?, ?, ?, ?)
                """,
                (flow_id, event.type, event.timestamp, event.timestamp + self.TTL_SECONDS, event.summary),
            )
            # Keep only the most recent events for the target flow.
            connection.execute(
                """
                DELETE FROM flow_events
                WHERE flow_id = ?
                  AND id NOT IN (
                      SELECT id
                      FROM flow_events
                      WHERE flow_id = ?
                      ORDER BY timestamp DESC, id DESC
                      LIMIT ?
                  )
                """,
                (flow_id, flow_id, self.MAX_EVENTS_PER_FLOW),
            )
            connection.commit()
        finally:
            connection.close()

        return event

    def get_since(self, flow_id: str, since: float) -> tuple[list[FlowEvent], bool]:
        """Return (events_after_since, settled).

        settled is True if:
        - No events exist for this flow, OR
        - A flow_settled event exists after `since`, OR
        - The most recent event is older than SETTLE_TIMEOUT seconds.
        """
        now = time.time()
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT event_type, timestamp, summary
                FROM flow_events
                WHERE flow_id = ? AND expires_at > ?
                ORDER BY timestamp ASC, id ASC
                """,
                (flow_id, now),
            ).fetchall()
        finally:
            connection.close()

        all_events = [
            FlowEvent(type=row["event_type"], timestamp=row["timestamp"], summary=row["summary"]) for row in rows
        ]

        after = [e for e in all_events if e.timestamp > since]

        if not after and not all_events:
            return [], True

        if any(e.type == "flow_settled" for e in after):
            return after, True

        last_event_age = time.time() - all_events[-1].timestamp
        settled = last_event_age >= self.SETTLE_TIMEOUT

        return after, settled

    async def teardown(self) -> None:
        return None

from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, get_args

from lfx.services.base import Service

EXTENSION_EVENT_TYPES = Literal[
    "bundle_reloaded",
    "components_added",
    "components_removed",
    "flow_migrated",
    "extension_error",
    "bundle_reload_failed",
]


@dataclass(frozen=True)
class ExtensionEvent:
    type: str
    timestamp: float
    payload: dict = field(default_factory=dict)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS extension_events (
    keyspace   TEXT NOT NULL DEFAULT 'global',
    ts         REAL NOT NULL,
    type       TEXT NOT NULL,
    payload    TEXT NOT NULL DEFAULT '{}',
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ext_events_keyspace_ts ON extension_events(keyspace, ts);
CREATE INDEX IF NOT EXISTS idx_ext_events_expires ON extension_events(expires_at);
"""


class ExtensionEventsService(Service):
    """SQLite-backed event queue for extension lifecycle events.

    Uses Python's stdlib sqlite3 in WAL mode for cross-worker visibility (multiple
    uvicorn/gunicorn workers share the same on-disk database file). TTL-based
    cleanup is performed lazily on each write and can be triggered explicitly
    via cleanup().

    Eviction policy:
    - TTL (120s): events older than TTL_SECONDS are purged lazily on every emit().
      A polling client that does not poll within the TTL window will miss those events.
    - Global cap (500 events): when MAX_EVENTS is exceeded, the oldest events are
      evicted (DELETE ... OFFSET MAX_EVENTS) regardless of TTL. This prevents
      unbounded growth if events accumulate faster than they are polled.

    Keyspaces:
    - "user:<id>": per-user events. The reload endpoint and Graph.from_payload
      derive this from the authenticated user so a poll on GET /extensions/events
      only returns events that user triggered.
    - "global": fallback for emission paths where no user is in scope
      (authless local dev, background tasks). Authenticated endpoints never
      read from "global" directly.
    """

    name = "extension_events_service"

    TTL_SECONDS: float = 120.0
    SETTLE_TIMEOUT: float = 10.0
    MAX_EVENTS: int = 500

    _VALID_EVENT_TYPES: frozenset[str] = frozenset(get_args(EXTENSION_EVENT_TYPES))

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        super().__init__()
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "langflow_extension_events"
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = cache_dir / "extension_events.sqlite"
        self._conn = sqlite3.connect(
            str(self._db_path),
            isolation_level=None,
            check_same_thread=False,
            timeout=5.0,
        )
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.executescript(_SCHEMA)

    def emit(self, event_type: str, payload: dict, keyspace: str = "global") -> ExtensionEvent:
        """Append an extension lifecycle event to the queue.

        Raises ValueError for unrecognised event types. The write also
        performs lazy TTL cleanup and enforces the global MAX_EVENTS cap.
        """
        if event_type not in self._VALID_EVENT_TYPES:
            msg = f"Invalid event type: {event_type!r}. Must be one of {sorted(self._VALID_EVENT_TYPES)}"
            raise ValueError(msg)

        now = time.time()
        event = ExtensionEvent(type=event_type, timestamp=now, payload=payload)
        expires_at = now + self.TTL_SECONDS
        payload_json = json.dumps(payload)

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute("DELETE FROM extension_events WHERE expires_at < ?", (now,))
                self._conn.execute(
                    "INSERT INTO extension_events (keyspace, ts, type, payload, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (keyspace, now, event_type, payload_json, expires_at),
                )
                # Enforce global cap: keep only the MAX_EVENTS most recent rows.
                self._conn.execute(
                    """
                    DELETE FROM extension_events
                    WHERE rowid IN (
                        SELECT rowid FROM extension_events
                        ORDER BY ts DESC, rowid DESC
                        LIMIT -1 OFFSET ?
                    )
                    """,
                    (self.MAX_EVENTS,),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

        return event

    def since(self, since_ts: float, keyspace: str = "global") -> tuple[list[ExtensionEvent], bool]:
        """Return (events_after_since_ts, settled) for the given keyspace.

        settled is True when:
        - No non-expired events exist for the keyspace, OR
        - The most recent event is older than SETTLE_TIMEOUT seconds.
        """
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT type, ts, payload
                FROM extension_events
                WHERE keyspace = ? AND expires_at >= ?
                ORDER BY ts ASC, rowid ASC
                """,
                (keyspace, now),
            ).fetchall()

        all_events = [ExtensionEvent(type=r[0], timestamp=r[1], payload=json.loads(r[2])) for r in rows]
        after = [e for e in all_events if e.timestamp > since_ts]

        if not all_events:
            return [], True

        last_event_age = now - all_events[-1].timestamp
        settled = last_event_age >= self.SETTLE_TIMEOUT

        return after, settled

    def cleanup(self) -> None:
        """Force-evict all expired events. Useful for tests and ops scripts."""
        now = time.time()
        with self._lock:
            self._conn.execute("DELETE FROM extension_events WHERE expires_at < ?", (now,))

    async def teardown(self) -> None:
        with self._lock:
            self._conn.close()

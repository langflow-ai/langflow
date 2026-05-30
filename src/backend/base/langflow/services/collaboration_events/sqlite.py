from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import time
import uuid
from pathlib import Path
from uuid import UUID

from langflow.services.collaboration_events.schemas import CollaborationEvent, CollaborationPollCursor
from langflow.services.collaboration_events.service import CollaborationEventService

_SCHEMA = """
CREATE TABLE IF NOT EXISTS collaboration_events (
    id         TEXT NOT NULL,
    flow_id    TEXT NOT NULL,
    created_at REAL NOT NULL,
    type       TEXT NOT NULL,
    payload    TEXT NOT NULL DEFAULT '{}',
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_collab_events_flow_created_id
    ON collaboration_events(flow_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_collab_events_expires ON collaboration_events(expires_at);
"""


class SQLiteCollaborationEventService(CollaborationEventService):
    """SQLite WAL-backed collaboration event mailbox keyed by ``flow_id``.

    Uses stdlib ``sqlite3`` so multiple uvicorn/gunicorn workers on the same host
    can share one cache-dir database file. This is polling-based fanout, not
    pub/sub.
    """

    TTL_SECONDS: float = 120.0
    MAX_EVENTS_PER_FLOW: int = 1000
    DEFAULT_POLL_LIMIT: int = 200

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "langflow_collaboration_events"
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = cache_dir / "collaboration_events.sqlite"
        self._conn = sqlite3.connect(
            str(self._db_path),
            isolation_level=None,
            check_same_thread=False,
            timeout=5.0,
        )
        # SQLite locks coordinate access across connections/processes. This lock
        # coordinates threads in this worker that share the same connection object.
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.executescript(_SCHEMA)

    def publish(self, flow_id: UUID, event_type: str, payload: dict) -> CollaborationEvent:
        flow_id_key = str(flow_id)
        if not event_type:
            msg = "event_type is required"
            raise ValueError(msg)
        if payload is None:
            msg = "payload must be a dict"
            raise TypeError(msg)

        event_id = str(uuid.uuid4())
        event_payload = dict(payload)
        payload_json = json.dumps(event_payload)

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                event = CollaborationEvent(
                    id=event_id,
                    flow_id=flow_id,
                    created_at=now,
                    type=event_type,
                    payload=event_payload,
                )
                expires_at = now + self.TTL_SECONDS
                self._purge_expired_locked(now)
                self._conn.execute(
                    """
                    INSERT INTO collaboration_events
                        (id, flow_id, created_at, type, payload, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (event_id, flow_id_key, now, event_type, payload_json, expires_at),
                )
                self._enforce_per_flow_cap_locked(flow_id_key)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

        return event

    def poll(
        self,
        flow_id: UUID,
        *,
        cursor: CollaborationPollCursor | None = None,
        limit: int | None = None,
    ) -> tuple[list[CollaborationEvent], CollaborationPollCursor]:
        flow_id_key = str(flow_id)

        poll_limit = self.DEFAULT_POLL_LIMIT if limit is None else limit
        if poll_limit < 1:
            msg = "limit must be at least 1"
            raise ValueError(msg)

        cursor = cursor or CollaborationPollCursor()
        # Match SQLite's cross-worker granularity: cleanup and read are separate statements,
        # not one local-only critical section that blocks same-worker publishes.
        with self._lock:
            now = time.time()
            self._purge_expired_locked(now)

        with self._lock:
            now = time.time()
            rows = self._conn.execute(
                """
                SELECT id, created_at, type, payload
                FROM collaboration_events
                WHERE flow_id = ?
                  AND expires_at >= ?
                  AND (
                        created_at > ?
                     OR (created_at = ? AND id > ?)
                  )
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (
                    flow_id_key,
                    now,
                    cursor.created_at,
                    cursor.created_at,
                    cursor.event_id,
                    poll_limit,
                ),
            ).fetchall()

        events = [
            CollaborationEvent(
                id=row[0],
                flow_id=flow_id,
                created_at=row[1],
                type=row[2],
                payload=json.loads(row[3]),
            )
            for row in rows
        ]

        if not events:
            return [], cursor

        last = events[-1]
        return events, CollaborationPollCursor(created_at=last.created_at, event_id=last.id)

    def cleanup(self) -> None:
        with self._lock:
            now = time.time()
            self._purge_expired_locked(now)

    async def teardown(self) -> None:
        with self._lock:
            self._conn.close()

    def _purge_expired_locked(self, now: float) -> None:
        self._conn.execute("DELETE FROM collaboration_events WHERE expires_at < ?", (now,))

    def _enforce_per_flow_cap_locked(self, flow_id: str) -> None:
        # SQLite: LIMIT -1 means no row cap; OFFSET skips the N newest rows so we delete older ones.
        self._conn.execute(
            """
            DELETE FROM collaboration_events
            WHERE rowid IN (
                SELECT rowid FROM collaboration_events
                WHERE flow_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (flow_id, self.MAX_EVENTS_PER_FLOW),
        )

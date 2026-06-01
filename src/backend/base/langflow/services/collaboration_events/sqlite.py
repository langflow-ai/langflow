from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import time
import uuid
from pathlib import Path
from uuid import UUID

from langflow.services.collaboration_events.schemas import (
    UNSET,
    CollaborationEvent,
    CollaborationPollCursor,
    CollaborationPresenceChange,
    CollaborationPresenceConnectionUser,
    CollaborationPresenceSnapshot,
    CollaborationSelectionTarget,
    CollaborationUserSelection,
)
from langflow.services.collaboration_events.service import CollaborationEventService

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id         TEXT NOT NULL,
    flow_id    TEXT NOT NULL,
    created_at REAL NOT NULL,
    type       TEXT NOT NULL,
    payload    TEXT NOT NULL DEFAULT '{}',
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_flow_created_id
    ON events(flow_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_events_expires ON events(expires_at);

CREATE TABLE IF NOT EXISTS connections (
    flow_id               TEXT NOT NULL,
    user_id               TEXT NOT NULL,
    connection_id         TEXT NOT NULL PRIMARY KEY,
    username              TEXT NOT NULL,
    profile_image         TEXT,
    selected_kind         TEXT,
    selected_id           TEXT,
    selected_at           REAL NOT NULL,
    expires_at            REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_connections_flow_expires
    ON connections(flow_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_connections_flow_user_selected
    ON connections(flow_id, user_id, selected_at);
CREATE INDEX IF NOT EXISTS idx_connections_expires
    ON connections(expires_at);
"""


class SQLiteCollaborationEventService(CollaborationEventService):
    """SQLite WAL-backed collaboration event mailbox keyed by ``flow_id``.

    Uses stdlib ``sqlite3`` so multiple uvicorn/gunicorn workers on the same host
    can share one cache-dir database file. This is polling-based fanout, not
    pub/sub.
    """

    TTL_SECONDS: float = 120.0
    PRESENCE_TTL_SECONDS: float = 30.0
    MAX_EVENTS_PER_FLOW: int = 1000
    DEFAULT_POLL_LIMIT: int = 200

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "langflow_collaboration"
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = cache_dir / "langflow_collaboration.sqlite"
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

    def publish(self, flow_id: UUID, event_type: str, payload: dict) -> CollaborationEvent:
        """Push an event for cross-worker fanout."""
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
                self._purge_expired_events_locked(now)
                self._conn.execute(
                    """
                    INSERT INTO events
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
        """Return events after ``cursor`` and the updated poll cursor."""
        flow_id_key = str(flow_id)

        poll_limit = self.DEFAULT_POLL_LIMIT if limit is None else limit
        if poll_limit < 1:
            msg = "limit must be at least 1"
            raise ValueError(msg)

        cursor = cursor or CollaborationPollCursor()
        with self._lock:
            now = time.time()
            self._purge_expired_events_locked(now)

        with self._lock:
            now = time.time()
            rows = self._conn.execute(
                """
                SELECT id, created_at, type, payload
                FROM events
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
        """Force-evict expired events and presence rows. Useful for tests and ops scripts."""
        with self._lock:
            now = time.time()
            self._purge_expired_locked(now)

    def add_connection(
        self,
        *,
        flow_id: UUID,
        user_id: UUID,
        connection_id: str,
        username: str,
        profile_image: str | None,
    ) -> CollaborationPresenceChange | None:
        """Create or replace an active connection row.

        Returns a `CollaborationPresenceChange` when the user-visible state changed,
        otherwise `None`.
        """
        flow_id_key = str(flow_id)
        user_id_key = str(user_id)

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                self._purge_expired_events_locked(now)
                before_user = self._effective_user_locked(flow_id_key, user_id_key, now)
                expires_at = now + self.PRESENCE_TTL_SECONDS
                self._conn.execute(
                    """
                    INSERT INTO connections (
                        flow_id, user_id, connection_id, username, profile_image,
                        selected_kind, selected_id, selected_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                    ON CONFLICT(connection_id) DO UPDATE SET
                        flow_id = excluded.flow_id,
                        user_id = excluded.user_id,
                        username = excluded.username,
                        profile_image = excluded.profile_image,
                        selected_kind = NULL,
                        selected_id = NULL,
                        selected_at = excluded.selected_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        flow_id_key,
                        user_id_key,
                        connection_id,
                        username,
                        profile_image,
                        now,
                        expires_at,
                    ),
                )
                after_user = self._effective_user_locked(flow_id_key, user_id_key, now)
                change = self._presence_change(user_id, before_user, after_user)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

        return change

    def update_connection(
        self,
        *,
        flow_id: UUID,
        connection_id: str,
        selected: CollaborationSelectionTarget | None | object = UNSET,
    ) -> CollaborationPresenceChange | None:
        """Refresh the TTL for an active connection and optionally update its selection.

        If `selected` is provided (not `UNSET`), it updates the connection's
        selection state. Returns `None` when only the TTL changed.
        """
        flow_id_key = str(flow_id)

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                self._purge_expired_events_locked(now)

                row = self._conn.execute(
                    """
                    SELECT user_id
                    FROM connections
                    WHERE flow_id = ? AND connection_id = ? AND expires_at >= ?
                    """,
                    (flow_id_key, connection_id, now),
                ).fetchone()
                if row is None:
                    self._conn.execute("COMMIT")
                    return None

                user_id_key = row[0]
                user_id = UUID(user_id_key)
                before_user = self._effective_user_locked(flow_id_key, user_id_key, now)
                expires_at = now + self.PRESENCE_TTL_SECONDS

                if selected is UNSET:
                    self._conn.execute(
                        """
                        UPDATE connections
                        SET expires_at = ?
                        WHERE flow_id = ? AND connection_id = ?
                        """,
                        (expires_at, flow_id_key, connection_id),
                    )
                else:
                    if selected is None:
                        selected_kind = None
                        selected_id = None
                        selected_at = now
                    else:
                        selected_kind = selected.kind
                        selected_id = selected.id
                        selected_at = now
                    self._conn.execute(
                        """
                        UPDATE connections
                        SET expires_at = ?,
                            selected_kind = ?,
                            selected_id = ?,
                            selected_at = ?
                        WHERE flow_id = ? AND connection_id = ?
                        """,
                        (
                            expires_at,
                            selected_kind,
                            selected_id,
                            selected_at,
                            flow_id_key,
                            connection_id,
                        ),
                    )

                after_user = self._effective_user_locked(flow_id_key, user_id_key, now)
                change = self._presence_change(user_id, before_user, after_user)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

        return change

    def remove_connection(
        self,
        *,
        flow_id: UUID,
        connection_id: str,
    ) -> CollaborationPresenceChange | None:
        """Remove an active connection row.

        Returns a `CollaborationPresenceChange` if the user fully left the flow,
        otherwise `None`.
        """
        flow_id_key = str(flow_id)

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                self._purge_expired_events_locked(now)

                row = self._conn.execute(
                    """
                    SELECT user_id
                    FROM connections
                    WHERE flow_id = ? AND connection_id = ?
                    """,
                    (flow_id_key, connection_id),
                ).fetchone()
                if row is None:
                    self._conn.execute("COMMIT")
                    return None

                user_id_key = row[0]
                user_id = UUID(user_id_key)
                before_user = self._effective_user_locked(flow_id_key, user_id_key, now)

                self._conn.execute(
                    """
                    DELETE FROM connections
                    WHERE flow_id = ? AND connection_id = ?
                    """,
                    (flow_id_key, connection_id),
                )

                after_user = self._effective_user_locked(flow_id_key, user_id_key, now)
                change = self._presence_change(user_id, before_user, after_user)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

        return change

    def list_users(self, flow_ids: list[UUID]) -> dict[UUID, CollaborationPresenceSnapshot]:
        """Return snapshots of active, deduplicated users and their effective selections, grouped by flow id."""
        if not flow_ids:
            msg = "flow_ids must not be empty"
            raise ValueError(msg)

        flow_id_keys = [str(flow_id) for flow_id in flow_ids]
        flow_ids_json = json.dumps(flow_id_keys)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                self._purge_expired_events_locked(now)
                self._conn.execute(
                    """
                    DELETE FROM connections
                    WHERE flow_id IN (SELECT value FROM json_each(?))
                      AND expires_at < ?
                    """,
                    (flow_ids_json, now),
                )
                snapshots = self._presence_snapshots_for_flows_locked(flow_id_keys, flow_ids_json, now)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

        return {flow_id: snapshots.get(flow_id, CollaborationPresenceSnapshot(users=[])) for flow_id in flow_ids}

    async def teardown(self) -> None:
        with self._lock:
            self._conn.close()

    def _purge_expired_locked(self, now: float) -> None:
        self._purge_expired_events_locked(now)
        self._purge_expired_connections_locked(now)

    def _purge_expired_events_locked(self, now: float) -> None:
        self._conn.execute("DELETE FROM events WHERE expires_at < ?", (now,))

    def _purge_expired_connections_locked(self, now: float) -> None:
        self._conn.execute("DELETE FROM connections WHERE expires_at < ?", (now,))

    def _enforce_per_flow_cap_locked(self, flow_id: str) -> None:
        self._conn.execute(
            """
            DELETE FROM events
            WHERE rowid IN (
                SELECT rowid FROM events
                WHERE flow_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (flow_id, self.MAX_EVENTS_PER_FLOW),
        )

    def _presence_snapshots_for_flows_locked(
        self,
        flow_id_keys: list[str],
        flow_ids_json: str,
        now: float,
    ) -> dict[UUID, CollaborationPresenceSnapshot]:
        rows = self._conn.execute(
            """
            SELECT
                flow_id,
                user_id,
                username,
                profile_image,
                selected_kind,
                selected_id
            FROM connections AS c
            WHERE flow_id IN (SELECT value FROM json_each(?))
              AND expires_at >= ?
            ORDER BY flow_id ASC, user_id ASC, selected_at DESC, connection_id ASC
            """,
            (flow_ids_json, now),
        ).fetchall()

        snapshots = {UUID(flow_id_key): CollaborationPresenceSnapshot(users=[]) for flow_id_key in flow_id_keys}
        seen_users: set[tuple[UUID, UUID]] = set()
        for row in rows:
            flow_id = UUID(row[0])
            user_id = UUID(row[1])
            user_key = (flow_id, user_id)
            if user_key in seen_users:
                continue
            seen_users.add(user_key)

            selected = self._selection_target(row[4], row[5])
            snapshots[flow_id].users.append(
                CollaborationPresenceConnectionUser(
                    user_id=user_id,
                    username=row[2],
                    profile_image=row[3],
                    selected=selected,
                )
            )

        return snapshots

    def _effective_user_locked(
        self,
        flow_id_key: str,
        user_id_key: str,
        now: float,
    ) -> CollaborationPresenceConnectionUser | None:
        """Return the active protocol-visible state for one user.

        This reads only that user's active connection rows. If multiple rows
        exist, the user is present once and their effective selection comes from
        the connection with the latest selection update.
        """
        rows = self._conn.execute(
            """
            SELECT username, profile_image, selected_kind, selected_id, selected_at
            FROM connections
            WHERE flow_id = ?
              AND user_id = ?
              AND expires_at >= ?
            ORDER BY selected_at DESC
            """,
            (flow_id_key, user_id_key, now),
        ).fetchall()
        if not rows:
            return None

        selected = None
        for row in rows:
            if row[4] is not None:
                selected = self._selection_target(row[2], row[3])
                break

        first = rows[0]
        return CollaborationPresenceConnectionUser(
            user_id=UUID(user_id_key),
            username=first[0],
            profile_image=first[1],
            selected=selected,
        )

    @staticmethod
    def _selection_target(kind: str | None, target_id: str | None) -> CollaborationSelectionTarget | None:
        if kind is None or target_id is None:
            return None
        return CollaborationSelectionTarget(kind=kind, id=target_id)

    def _presence_change(
        self,
        user_id: UUID,
        before_user: CollaborationPresenceConnectionUser | None,
        after_user: CollaborationPresenceConnectionUser | None,
    ) -> CollaborationPresenceChange | None:
        """Determine what effectively changed for a specific user.

        Connection rows are internal. Clients only care whether the user became
        visible, disappeared, or changed the selected node/edge.
        """
        if before_user is None and after_user is not None:  # user's first connection
            return CollaborationPresenceChange(joined=after_user)

        if before_user is not None and after_user is None:  # user has disconnected
            return CollaborationPresenceChange(left_user_id=user_id)

        if before_user is not None and after_user is not None and before_user.selected != after_user.selected:
            return CollaborationPresenceChange(
                selection_updated=CollaborationUserSelection(user_id=user_id, selected=after_user.selected)
            )

        return None

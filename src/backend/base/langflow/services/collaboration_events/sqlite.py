from __future__ import annotations

import asyncio
import json
import tempfile
import time
import uuid
from pathlib import Path
from uuid import UUID

import aiosqlite
from lfx.log.logger import logger

from langflow.services.collaboration_events.schemas import (
    UNSET,
    CollaborationEvent,
    CollaborationPollCursor,
    CollaborationPresenceChange,
    CollaborationPresenceChangeEnvelope,
    CollaborationPresenceConnectionUser,
    CollaborationPresenceSnapshot,
    CollaborationSelectionTarget,
    CollaborationUserSelection,
)
from langflow.services.collaboration_events.service import CollaborationEventService

_LOG_PREFIX = "[Collaboration Events (SQLite)] "

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

    Uses ``aiosqlite`` so multiple uvicorn/gunicorn workers on the same host
    can share one cache-dir database file.
    """

    TTL_SECONDS: float = 120.0
    PRESENCE_TTL_SECONDS: float = 90.0
    MAX_EVENTS_PER_FLOW: int = 1000
    DEFAULT_POLL_LIMIT: int = 200

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        *,
        presence_ttl_seconds: float | None = None,
    ) -> None:
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "langflow_collaboration"
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        if presence_ttl_seconds is not None:
            self.PRESENCE_TTL_SECONDS = presence_ttl_seconds
        self._db_path = cache_dir / "langflow_collaboration.sqlite"
        self._conn: aiosqlite.Connection | None = None
        self._init_lock = asyncio.Lock()
        self._lock = asyncio.Lock()

    async def _ensure_conn(self) -> aiosqlite.Connection:
        if self._conn is not None:
            return self._conn
        async with self._init_lock:
            if self._conn is not None:
                return self._conn
            conn = await aiosqlite.connect(
                str(self._db_path),
                isolation_level=None,
                timeout=5.0,
            )
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA busy_timeout=5000")
            await conn.executescript(_SCHEMA)
            self._conn = conn
            return conn

    async def publish(self, flow_id: UUID, event_type: str, payload: dict) -> CollaborationEvent:
        """Push an event for cross-worker fanout."""
        flow_id_key = str(flow_id)
        if not event_type:
            msg = "event_type is required"
            raise ValueError(msg)
        if payload is None:
            msg = "payload must be a dict"
            raise TypeError(msg)

        event_id = uuid.uuid4()
        event_id_key = str(event_id)
        event_payload = dict(payload)
        payload_json = json.dumps(event_payload)

        async with self._lock:
            conn = await self._ensure_conn()
            await conn.execute("BEGIN IMMEDIATE")
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
                await self._purge_expired_events_locked(conn, now)
                await conn.execute(
                    """
                    INSERT INTO events
                        (id, flow_id, created_at, type, payload, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (event_id_key, flow_id_key, now, event_type, payload_json, expires_at),
                )
                await self._enforce_per_flow_cap_locked(conn, flow_id_key)
                await conn.execute("COMMIT")
                await logger.adebug(
                    "%sPublished collaboration event %s for flow %s (event_id: %s)",
                    _LOG_PREFIX,
                    event_type,
                    flow_id_key,
                    event_id_key,
                )
            except Exception as exc:
                await conn.execute("ROLLBACK")
                await logger.aerror(
                    "%sFailed to publish collaboration event %s for flow %s: %s",
                    _LOG_PREFIX,
                    event_type,
                    flow_id_key,
                    exc,
                )
                raise

        return event

    async def poll(
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
        cursor_event_id_key = str(cursor.event_id) if cursor.event_id is not None else ""
        async with self._lock:
            conn = await self._ensure_conn()
            now = time.time()
            await self._purge_expired_events_locked(conn, now)

            rows = await (
                await conn.execute(
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
                        cursor_event_id_key,
                        poll_limit,
                    ),
                )
            ).fetchall()

        events = [
            CollaborationEvent(
                id=UUID(row[0]),
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

    async def cleanup(self) -> None:
        """Force-evict expired events and presence rows. Useful for tests and ops scripts."""
        async with self._lock:
            conn = await self._ensure_conn()
            now = time.time()
            await self._purge_expired_locked(conn, now)
            await logger.adebug("%sCompleted collaboration events cleanup", _LOG_PREFIX)

    async def add_connection(
        self,
        *,
        flow_id: UUID,
        user_id: UUID,
        connection_id: UUID,
        username: str,
        profile_image: str | None,
    ) -> CollaborationPresenceChange | None:
        """Create or replace an active connection row.

        Returns a `CollaborationPresenceChange` when the user-visible state changed,
        otherwise `None`.
        """
        flow_id_key = str(flow_id)
        user_id_key = str(user_id)
        connection_id_key = str(connection_id)
        change: CollaborationPresenceChange | None = None

        async with self._lock:
            conn = await self._ensure_conn()
            await conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                await self._purge_expired_events_locked(conn, now)
                before_user = await self._effective_user_locked(conn, flow_id_key, user_id_key, now)
                expires_at = now + self.PRESENCE_TTL_SECONDS
                await conn.execute(
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
                        connection_id_key,
                        username,
                        profile_image,
                        now,
                        expires_at,
                    ),
                )
                after_user = await self._effective_user_locked(conn, flow_id_key, user_id_key, now)
                change = self._presence_change(user_id, before_user, after_user)
                await conn.execute("COMMIT")
            except Exception:
                await conn.execute("ROLLBACK")
                raise

        return change

    async def update_connection(
        self,
        *,
        connection_id: UUID,
        selected: CollaborationSelectionTarget | None | object = UNSET,
    ) -> CollaborationPresenceChange | None:
        """Refresh the TTL for an active connection and optionally update its selection.

        If `selected` is provided (not `UNSET`), it updates the connection's
        selection state. Returns `None` when only the TTL changed.
        """
        connection_id_key = str(connection_id)
        change: CollaborationPresenceChange | None = None

        async with self._lock:
            conn = await self._ensure_conn()
            await conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                await self._purge_expired_events_locked(conn, now)

                row = await (
                    await conn.execute(
                        """
                        SELECT flow_id, user_id
                        FROM connections
                        WHERE connection_id = ? AND expires_at >= ?
                        """,
                        (connection_id_key, now),
                    )
                ).fetchone()
                if row is None:
                    await conn.execute("COMMIT")
                    return None

                flow_id_key = row[0]
                user_id_key = row[1]
                user_id = UUID(user_id_key)
                before_user = await self._effective_user_locked(conn, flow_id_key, user_id_key, now)
                expires_at = now + self.PRESENCE_TTL_SECONDS

                if selected is UNSET:
                    await conn.execute(
                        """
                        UPDATE connections
                        SET expires_at = ?
                        WHERE connection_id = ?
                        """,
                        (expires_at, connection_id_key),
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
                    await conn.execute(
                        """
                        UPDATE connections
                        SET expires_at = ?,
                            selected_kind = ?,
                            selected_id = ?,
                            selected_at = ?
                        WHERE connection_id = ?
                        """,
                        (
                            expires_at,
                            selected_kind,
                            selected_id,
                            selected_at,
                            connection_id_key,
                        ),
                    )

                after_user = await self._effective_user_locked(conn, flow_id_key, user_id_key, now)
                change = self._presence_change(user_id, before_user, after_user)
                await conn.execute("COMMIT")
            except Exception:
                await conn.execute("ROLLBACK")
                raise

        return change

    async def remove_connection(
        self,
        *,
        connection_id: UUID,
    ) -> CollaborationPresenceChange | None:
        """Remove an active connection row.

        Returns a `CollaborationPresenceChange` if the user fully left the flow,
        otherwise `None`.
        """
        connection_id_key = str(connection_id)
        change: CollaborationPresenceChange | None = None

        async with self._lock:
            conn = await self._ensure_conn()
            await conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                await self._purge_expired_events_locked(conn, now)

                row = await (
                    await conn.execute(
                        """
                        SELECT flow_id, user_id
                        FROM connections
                        WHERE connection_id = ?
                        """,
                        (connection_id_key,),
                    )
                ).fetchone()
                if row is None:
                    await conn.execute("COMMIT")
                    return None

                flow_id_key = row[0]
                user_id_key = row[1]
                user_id = UUID(user_id_key)
                before_user = await self._effective_user_locked(conn, flow_id_key, user_id_key, now)

                await conn.execute(
                    """
                    DELETE FROM connections
                    WHERE connection_id = ?
                    """,
                    (connection_id_key,),
                )

                after_user = await self._effective_user_locked(conn, flow_id_key, user_id_key, now)
                change = self._presence_change(user_id, before_user, after_user)
                await conn.execute("COMMIT")
            except Exception:
                await conn.execute("ROLLBACK")
                raise

        return change

    async def remove_connections(self, connection_ids: list[UUID]) -> list[CollaborationPresenceChangeEnvelope]:
        """Remove active connection rows in one transaction."""
        if not connection_ids:
            return []

        connection_id_keys = [str(connection_id) for connection_id in connection_ids]
        connection_ids_json = json.dumps(connection_id_keys)
        changes: list[CollaborationPresenceChangeEnvelope] = []

        async with self._lock:
            conn = await self._ensure_conn()
            await conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                await self._purge_expired_events_locked(conn, now)

                affected_users = await self._affected_users_for_connections_locked(conn, connection_ids_json)
                if not affected_users:
                    await conn.execute("COMMIT")
                    return []

                affected_users_json = json.dumps(
                    [{"flow_id": flow_id_key, "user_id": user_id_key} for flow_id_key, user_id_key in affected_users]
                )
                before_users = await self._effective_users_for_keys_locked(conn, affected_users_json, now)
                await conn.execute(
                    """
                    DELETE FROM connections
                    WHERE connection_id IN (SELECT value FROM json_each(?))
                    """,
                    (connection_ids_json,),
                )
                after_users = await self._effective_users_for_keys_locked(conn, affected_users_json, now)

                for flow_id_key, user_id_key in affected_users:
                    flow_id = UUID(flow_id_key)
                    user_id = UUID(user_id_key)
                    user_key = (flow_id_key, user_id_key)
                    change = self._presence_change(user_id, before_users.get(user_key), after_users.get(user_key))
                    if change is not None:
                        changes.append(CollaborationPresenceChangeEnvelope(flow_id=flow_id, change=change))

                await conn.execute("COMMIT")
            except Exception:
                await conn.execute("ROLLBACK")
                raise

        return changes

    async def list_users(self, flow_ids: list[UUID]) -> dict[UUID, CollaborationPresenceSnapshot]:
        """Return snapshots of active, deduplicated users and their effective selections, grouped by flow id."""
        if not flow_ids:
            msg = "flow_ids must not be empty"
            raise ValueError(msg)

        flow_id_keys = [str(flow_id) for flow_id in flow_ids]
        flow_ids_json = json.dumps(flow_id_keys)

        async with self._lock:
            conn = await self._ensure_conn()
            await conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                await self._purge_expired_events_locked(conn, now)
                await conn.execute(
                    """
                    DELETE FROM connections
                    WHERE flow_id IN (SELECT value FROM json_each(?))
                      AND expires_at < ?
                    """,
                    (flow_ids_json, now),
                )
                snapshots = await self._presence_snapshots_for_flows_locked(conn, flow_id_keys, flow_ids_json, now)
                await conn.execute("COMMIT")
            except Exception:
                await conn.execute("ROLLBACK")
                raise

        return {flow_id: snapshots.get(flow_id, CollaborationPresenceSnapshot(users=[])) for flow_id in flow_ids}

    async def teardown(self) -> None:
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None

    async def _purge_expired_locked(self, conn: aiosqlite.Connection, now: float) -> None:
        await self._purge_expired_events_locked(conn, now)
        await self._purge_expired_connections_locked(conn, now)

    async def _purge_expired_events_locked(self, conn: aiosqlite.Connection, now: float) -> None:
        await conn.execute("DELETE FROM events WHERE expires_at < ?", (now,))

    async def _purge_expired_connections_locked(self, conn: aiosqlite.Connection, now: float) -> None:
        await conn.execute("DELETE FROM connections WHERE expires_at < ?", (now,))

    async def _enforce_per_flow_cap_locked(self, conn: aiosqlite.Connection, flow_id: str) -> None:
        await conn.execute(
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

    async def _affected_users_for_connections_locked(
        self, conn: aiosqlite.Connection, connection_ids_json: str
    ) -> list[tuple[str, str]]:
        rows = await (
            await conn.execute(
                """
                WITH requested(connection_id) AS (
                    SELECT DISTINCT value
                    FROM json_each(?)
                )
                SELECT DISTINCT c.flow_id, c.user_id
                FROM connections AS c
                JOIN requested AS r ON r.connection_id = c.connection_id
                ORDER BY c.flow_id ASC, c.user_id ASC
                """,
                (connection_ids_json,),
            )
        ).fetchall()
        return [(row[0], row[1]) for row in rows]

    async def _effective_users_for_keys_locked(
        self,
        conn: aiosqlite.Connection,
        user_keys_json: str,
        now: float,
    ) -> dict[tuple[str, str], CollaborationPresenceConnectionUser]:
        rows = await (
            await conn.execute(
                """
                WITH affected(flow_id, user_id) AS (
                    SELECT DISTINCT
                        json_extract(value, '$.flow_id'),
                        json_extract(value, '$.user_id')
                    FROM json_each(?)
                )
                SELECT
                    c.flow_id,
                    c.user_id,
                    c.username,
                    c.profile_image,
                    c.selected_kind,
                    c.selected_id,
                    MAX(c.selected_at)
                FROM connections AS c
                JOIN affected AS a
                    ON a.flow_id = c.flow_id
                   AND a.user_id = c.user_id
                WHERE c.expires_at >= ?
                GROUP BY c.flow_id, c.user_id
                ORDER BY c.flow_id ASC, c.user_id ASC
                """,
                (user_keys_json, now),
            )
        ).fetchall()

        users: dict[tuple[str, str], CollaborationPresenceConnectionUser] = {}
        for row in rows:
            selected = self._selection_target(row[4], row[5])
            users[(row[0], row[1])] = CollaborationPresenceConnectionUser(
                user_id=UUID(row[1]),
                username=row[2],
                profile_image=row[3],
                selected=selected,
            )
        return users

    async def _presence_snapshots_for_flows_locked(
        self,
        conn: aiosqlite.Connection,
        flow_id_keys: list[str],
        flow_ids_json: str,
        now: float,
    ) -> dict[UUID, CollaborationPresenceSnapshot]:
        rows = await (
            await conn.execute(
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
            )
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

    async def _effective_user_locked(
        self,
        conn: aiosqlite.Connection,
        flow_id_key: str,
        user_id_key: str,
        now: float,
    ) -> CollaborationPresenceConnectionUser | None:
        """Return the active protocol-visible state for one user.

        This reads only that user's active connection rows. If multiple rows
        exist, the user is present once and their effective selection comes from
        the connection with the latest selection update.
        """
        rows = await (
            await conn.execute(
                """
            SELECT username, profile_image, selected_kind, selected_id, selected_at
            FROM connections
            WHERE flow_id = ?
              AND user_id = ?
              AND expires_at >= ?
            ORDER BY selected_at DESC
            """,
                (flow_id_key, user_id_key, now),
            )
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

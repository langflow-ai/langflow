"""Durable CheckpointStore on the same SQLite file as the job store (LE-1695).

The checkpoint travels as its own JSON payload (``GraphCheckpoint`` already guarantees
JSON round-trip safety), so the row is schema-stable across checkpoint model changes.
Expired checkpoints are filtered at read time, mirroring the in-memory store.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.graph.checkpoint.store import CheckpointStore

if TYPE_CHECKING:
    from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    session_id TEXT,
    job_id TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_run ON checkpoints(run_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON checkpoints(session_id);
CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    job_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    blob TEXT NOT NULL,
    PRIMARY KEY (job_id, kind)
);
"""

_NOT_EXPIRED = "(expires_at IS NULL OR expires_at > ?)"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteCheckpointStore(CheckpointStore):
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    async def _run(self, fn):
        def call():
            with self._connect() as conn:
                return fn(conn)

        return await asyncio.to_thread(call)

    async def save(self, checkpoint: GraphCheckpoint) -> None:
        def op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints"
                " (checkpoint_id, run_id, session_id, job_id, expires_at, created_at, payload)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    checkpoint.checkpoint_id,
                    checkpoint.run_id,
                    checkpoint.session_id,
                    checkpoint.job_id,
                    checkpoint.expires_at.isoformat() if checkpoint.expires_at else None,
                    _utcnow(),
                    checkpoint.model_dump_json(),
                ),
            )

        await self._run(op)

    async def load(self, checkpoint_id: str) -> GraphCheckpoint | None:
        def op(conn: sqlite3.Connection) -> str | None:
            row = conn.execute(
                f"SELECT payload FROM checkpoints WHERE checkpoint_id = ? AND {_NOT_EXPIRED}",  # noqa: S608
                (checkpoint_id, _utcnow()),
            ).fetchone()
            return row["payload"] if row else None

        payload = await self._run(op)
        return GraphCheckpoint.model_validate_json(payload) if payload else None

    async def delete(self, checkpoint_id: str) -> None:
        def op(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,))

        await self._run(op)

    async def load_by_run_id(self, run_id: str) -> GraphCheckpoint | None:
        def op(conn: sqlite3.Connection) -> str | None:
            row = conn.execute(
                f"SELECT payload FROM checkpoints WHERE run_id = ? AND {_NOT_EXPIRED}"  # noqa: S608
                " ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (run_id, _utcnow()),
            ).fetchone()
            return row["payload"] if row else None

        payload = await self._run(op)
        return GraphCheckpoint.model_validate_json(payload) if payload else None

    async def list_by_session(self, session_id: str) -> list[GraphCheckpoint]:
        def op(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                f"SELECT payload FROM checkpoints WHERE session_id = ? AND {_NOT_EXPIRED} ORDER BY rowid",  # noqa: S608
                (session_id, _utcnow()),
            ).fetchall()
            return [row["payload"] for row in rows]

        payloads = await self._run(op)
        return [GraphCheckpoint.model_validate_json(payload) for payload in payloads]

    async def save_blob(self, job_id: str, kind: str, blob: str) -> None:
        def op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT OR REPLACE INTO checkpoint_blobs (job_id, kind, blob) VALUES (?, ?, ?)",
                (job_id, kind, blob),
            )

        await self._run(op)

    async def load_blob(self, job_id: str, kind: str) -> str | None:
        def op(conn: sqlite3.Connection) -> str | None:
            row = conn.execute(
                "SELECT blob FROM checkpoint_blobs WHERE job_id = ? AND kind = ?",
                (job_id, kind),
            ).fetchone()
            return row["blob"] if row else None

        return await self._run(op)

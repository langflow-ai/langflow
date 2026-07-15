"""SQLite-backed durable job store (LE-1695 single-node default backend).

Why stdlib SQLite: zero new dependencies, one crash-safe file, real transactions for the
single-flight claims (``UPDATE ... WHERE status = ?``), and identical behavior on
Linux/macOS/Windows. ``sqlite3`` is synchronous, so every operation runs in a worker
thread (``asyncio.to_thread``) on a short-lived connection; WAL + ``busy_timeout`` absorb
single-node concurrency. Writes that must be atomic across statements (seq allocation,
metadata merge) run under ``BEGIN IMMEDIATE``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.services.durable.models import DurableEvent, DurableJob, DurableSignal, JobStatus, JobType, SignalType

if TYPE_CHECKING:
    from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    flow_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT,
    error TEXT,
    job_metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE TABLE IF NOT EXISTS job_events (
    job_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (job_id, seq)
);
CREATE TABLE IF NOT EXISTS signals (
    signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    consumed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signals_job_consumed ON signals(job_id, consumed);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(raw: str) -> datetime:
    return datetime.fromisoformat(raw)


class SqliteDurableJobStore:
    """Durable jobs + seq-ordered event log + control signals on one SQLite file."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(self._connect()) as conn, conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    async def _run(self, fn, *args):
        def call():
            # sqlite3's context manager commits/rolls back but never closes; close
            # explicitly or every op leaks a connection until GC.
            with contextlib.closing(self._connect()) as conn, conn:
                return fn(conn, *args)

        return await asyncio.to_thread(call)

    async def create_job(
        self,
        *,
        job_id: str,
        flow_id: str,
        user_id: str,
        job_type: JobType = JobType.WORKFLOW,
    ) -> None:
        def op(conn: sqlite3.Connection) -> None:
            now = _utcnow()
            try:
                conn.execute(
                    "INSERT INTO jobs (job_id, flow_id, user_id, job_type, status, job_metadata,"
                    " created_at, updated_at) VALUES (?, ?, ?, ?, ?, '{}', ?, ?)",
                    (job_id, flow_id, user_id, job_type.value, JobStatus.QUEUED.value, now, now),
                )
            except sqlite3.IntegrityError as exc:
                msg = f"Job {job_id} already exists"
                raise ValueError(msg) from exc

        await self._run(op)

    async def get_job(self, job_id: str) -> DurableJob | None:
        def op(conn: sqlite3.Connection) -> DurableJob | None:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return _job_from_row(row) if row else None

        return await self._run(op)

    async def update_status(self, job_id: str, status: JobStatus) -> None:
        def op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                (status.value, _utcnow(), job_id),
            )

        await self._run(op)

    async def set_result(self, job_id: str, result: dict[str, Any] | None) -> None:
        def op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE jobs SET result = ?, status = ?, updated_at = ? WHERE job_id = ?",
                (json.dumps(result), JobStatus.COMPLETED.value, _utcnow(), job_id),
            )

        await self._run(op)

    async def set_error(self, job_id: str, error: dict[str, Any]) -> None:
        def op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE jobs SET error = ?, status = ?, updated_at = ? WHERE job_id = ?",
                (json.dumps(error), JobStatus.FAILED.value, _utcnow(), job_id),
            )

        await self._run(op)

    async def update_metadata(self, job_id: str, patch: dict[str, Any]) -> None:
        def op(conn: sqlite3.Connection) -> None:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT job_metadata FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            merged = {**(json.loads(row["job_metadata"]) if row else {}), **patch}
            conn.execute(
                "UPDATE jobs SET job_metadata = ?, updated_at = ? WHERE job_id = ?",
                (json.dumps(merged), _utcnow(), job_id),
            )

        await self._run(op)

    async def append_event(self, job_id: str, event_type: str, payload: dict[str, Any]) -> int:
        def op(conn: sqlite3.Connection) -> int:
            # BEGIN IMMEDIATE serializes writers so MAX(seq)+1 is race-free (gap-free per job).
            conn.execute("BEGIN IMMEDIATE")
            # Two statements instead of INSERT...RETURNING: RETURNING needs SQLite >= 3.35,
            # which older bundled interpreters (Linux/Windows CPython) may not have.
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM job_events WHERE job_id = ?", (job_id,)
            ).fetchone()
            next_seq = int(row["next_seq"])
            conn.execute(
                "INSERT INTO job_events (job_id, seq, event_type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (job_id, next_seq, event_type, json.dumps(payload), _utcnow()),
            )
            return next_seq

        return await self._run(op)

    async def read_events(self, job_id: str, after_seq: int = 0) -> list[DurableEvent]:
        def op(conn: sqlite3.Connection) -> list[DurableEvent]:
            rows = conn.execute(
                "SELECT * FROM job_events WHERE job_id = ? AND seq > ? ORDER BY seq",
                (job_id, after_seq),
            ).fetchall()
            return [
                DurableEvent(
                    job_id=row["job_id"],
                    seq=row["seq"],
                    event_type=row["event_type"],
                    payload=json.loads(row["payload"]),
                    created_at=_parse_dt(row["created_at"]),
                )
                for row in rows
            ]

        return await self._run(op)

    async def write_signal(self, job_id: str, signal_type: SignalType, data: dict[str, Any] | None = None) -> None:
        def op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO signals (job_id, signal_type, data, created_at) VALUES (?, ?, ?, ?)",
                (job_id, signal_type.value, json.dumps(data or {}), _utcnow()),
            )

        await self._run(op)

    async def unconsumed_signals(self, job_id: str) -> list[DurableSignal]:
        def op(conn: sqlite3.Connection) -> list[DurableSignal]:
            rows = conn.execute(
                "SELECT * FROM signals WHERE job_id = ? AND consumed = 0 ORDER BY signal_id",
                (job_id,),
            ).fetchall()
            return [
                DurableSignal(
                    signal_id=row["signal_id"],
                    job_id=row["job_id"],
                    signal_type=SignalType(row["signal_type"]),
                    data=json.loads(row["data"]),
                    created_at=_parse_dt(row["created_at"]),
                )
                for row in rows
            ]

        return await self._run(op)

    async def consume_signals(self, job_id: str, signal_type: SignalType) -> int:
        def op(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(
                "UPDATE signals SET consumed = 1 WHERE job_id = ? AND signal_type = ? AND consumed = 0",
                (job_id, signal_type.value),
            )
            return cursor.rowcount

        return await self._run(op)

    async def claim_suspended_for_resume(self, job_id: str) -> bool:
        def op(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ? AND status = ?",
                (JobStatus.IN_PROGRESS.value, _utcnow(), job_id, JobStatus.SUSPENDED.value),
            )
            return cursor.rowcount == 1

        return await self._run(op)

    async def suspended_job_ids_for_flow(self, flow_id: str) -> list[str]:
        def op(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                "SELECT job_id FROM jobs WHERE flow_id = ? AND status = ? AND job_type = ? ORDER BY created_at",
                (flow_id, JobStatus.SUSPENDED.value, JobType.WORKFLOW.value),
            ).fetchall()
            return [row["job_id"] for row in rows]

        return await self._run(op)

    async def queued_workflow_job_ids(self) -> list[str]:
        def op(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                "SELECT job_id FROM jobs WHERE status = ? AND job_type = ? ORDER BY created_at",
                (JobStatus.QUEUED.value, JobType.WORKFLOW.value),
            ).fetchall()
            return [row["job_id"] for row in rows]

        return await self._run(op)


def _job_from_row(row: sqlite3.Row) -> DurableJob:
    return DurableJob(
        job_id=row["job_id"],
        flow_id=row["flow_id"],
        user_id=row["user_id"],
        status=JobStatus(row["status"]),
        job_type=JobType(row["job_type"]),
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
        result=json.loads(row["result"]) if row["result"] else None,
        error=json.loads(row["error"]) if row["error"] else None,
        job_metadata=json.loads(row["job_metadata"]),
    )

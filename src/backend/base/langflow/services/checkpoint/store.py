"""Durable, job-scoped graph CheckpointStore (LE-1441).

Persists a paused graph's ``GraphCheckpoint`` through the ``JobService``
checkpoint helper (one JSON row per ``(job_id, "graph")``), so a checkpoint
survives a process restart. The in-memory store (LE-1440) stays the standalone
default; this is wired as ``CHECKPOINT_SERVICE`` inside the running app.

Cross-row ABC lookups (by checkpoint id, run id, session id) deserialize the
graph-kind rows and filter in Python — the helper is job-keyed and never parses
the blob. The scanned set is bounded: one row per actively-suspended job.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.graph.checkpoint.store import CheckpointStore
from lfx.services.base import Service
from pydantic import ValidationError

if TYPE_CHECKING:
    from langflow.services.jobs.service import JobService

_KIND = "graph"


def _expired(checkpoint: GraphCheckpoint) -> bool:
    return checkpoint.expires_at is not None and checkpoint.expires_at <= datetime.now(timezone.utc)


def _as_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        return None


def _decode(blob: str) -> GraphCheckpoint | None:
    try:
        return GraphCheckpoint.model_validate_json(blob)
    except ValidationError:
        return None


class JobScopedCheckpointStore(CheckpointStore, Service):
    name = "checkpoint_service"  # registry key for ServiceType.CHECKPOINT_SERVICE

    def __init__(self, job_service: JobService) -> None:
        super().__init__()
        self._jobs = job_service

    async def teardown(self) -> None:
        pass

    async def save_blob(self, job_id: str, kind: str, blob: str) -> None:
        """Durably persist the agent-thread blob (LE-1447) on the job-scoped row."""
        parsed = _as_uuid(job_id)
        if parsed is not None:
            await self._jobs.save_checkpoint(parsed, kind, blob)

    async def load_blob(self, job_id: str, kind: str) -> str | None:
        parsed = _as_uuid(job_id)
        if parsed is None:
            return None
        return await self._jobs.load_checkpoint(parsed, kind)

    async def save(self, checkpoint: GraphCheckpoint) -> None:
        if checkpoint.job_id is None:
            msg = "GraphCheckpoint.job_id is required to persist a durable checkpoint"
            raise ValueError(msg)
        await self._jobs.save_checkpoint(UUID(checkpoint.job_id), _KIND, checkpoint.model_dump_json())

    async def load(self, checkpoint_id: str) -> GraphCheckpoint | None:
        for _job_id, checkpoint in await self._all():
            if checkpoint.checkpoint_id == checkpoint_id:
                return None if _expired(checkpoint) else checkpoint
        return None

    async def delete(self, checkpoint_id: str) -> None:
        for job_id, checkpoint in await self._all():
            if checkpoint.checkpoint_id == checkpoint_id:
                await self._jobs.delete_checkpoint(job_id, _KIND)
                return

    async def load_by_run_id(self, run_id: str) -> GraphCheckpoint | None:
        # run_id carries the job_id (LE-1446 threads it), so resume resolves the
        # one job-scoped row directly instead of scanning every stored checkpoint.
        job_id = _as_uuid(run_id)
        if job_id is None:
            return None
        blob = await self._jobs.load_checkpoint(job_id, _KIND)
        if blob is None:
            return None
        checkpoint = _decode(blob)
        if checkpoint is None or _expired(checkpoint):
            return None
        return checkpoint

    async def list_by_session(self, session_id: str) -> list[GraphCheckpoint]:
        return [cp for _job_id, cp in await self._all() if cp.session_id == session_id and not _expired(cp)]

    async def _all(self) -> list[tuple[UUID, GraphCheckpoint]]:
        """Decode every stored ``graph`` checkpoint across ALL jobs/users.

        This scan is NOT tenant-scoped (the row has no user_id; the store has no
        request user). The callers that use it — ``load(checkpoint_id)``,
        ``delete(checkpoint_id)``, ``list_by_session`` — must therefore never be
        exposed to a cross-user request: the durable multi-tenant resume path uses
        only ``load_by_run_id`` (job-scoped) behind ``resume_job``'s ownership
        check. Adding a user filter here would require threading the user through
        the CheckpointStore ABC.
        """
        decoded = []
        for job_id, blob in await self._jobs.all_checkpoints(_KIND):
            checkpoint = _decode(blob)
            # A row that no longer decodes (foreign/corrupt blob) is treated as
            # absent rather than failing every cross-row lookup.
            if checkpoint is not None:
                decoded.append((job_id, checkpoint))
        return decoded

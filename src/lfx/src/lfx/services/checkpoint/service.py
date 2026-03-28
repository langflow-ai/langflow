"""Checkpoint store implementations for graph pause/resume."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from lfx.services.checkpoint.schema import GraphCheckpoint


class CheckpointStore(ABC):
    """Abstract interface for checkpoint persistence."""

    @abstractmethod
    async def save(self, checkpoint: GraphCheckpoint) -> str:
        """Persist a checkpoint. Returns checkpoint_id."""
        ...

    @abstractmethod
    async def load(self, checkpoint_id: str) -> GraphCheckpoint | None:
        """Load a checkpoint by ID. Returns None if expired/missing."""
        ...

    @abstractmethod
    async def delete(self, checkpoint_id: str) -> None:
        """Delete a checkpoint (after successful resumption)."""
        ...

    @abstractmethod
    async def load_by_run_id(self, run_id: str) -> GraphCheckpoint | None:
        """Load the most recent checkpoint for a run/job. Returns None if not found."""
        ...

    @abstractmethod
    async def list_by_session(self, session_id: str) -> list[GraphCheckpoint]:
        """List checkpoints for a session."""
        ...


class InMemoryCheckpointStore(CheckpointStore):
    """Dict-backed checkpoint store for testing and single-process use.

    WARNING: This store holds checkpoints in process memory only. Checkpoints
    are lost on server restart and are invisible to other workers. This means:
      - Pause/resume will NOT work with multiple uvicorn/gunicorn workers.
      - Checkpoints do NOT survive server restarts.
    Use DatabaseCheckpointStore for production multi-worker deployments.
    """

    def __init__(self) -> None:
        self._store: dict[str, GraphCheckpoint] = {}

    async def save(self, checkpoint: GraphCheckpoint) -> str:
        self._store[checkpoint.checkpoint_id] = checkpoint
        return checkpoint.checkpoint_id

    async def load(self, checkpoint_id: str) -> GraphCheckpoint | None:
        checkpoint = self._store.get(checkpoint_id)
        if checkpoint is None:
            return None
        if checkpoint.expires_at and checkpoint.expires_at < datetime.now(timezone.utc):
            del self._store[checkpoint_id]
            return None
        return checkpoint

    async def delete(self, checkpoint_id: str) -> None:
        self._store.pop(checkpoint_id, None)

    async def load_by_run_id(self, run_id: str) -> GraphCheckpoint | None:
        now = datetime.now(timezone.utc)
        matches = [
            cp
            for cp in self._store.values()
            if cp.run_id == run_id and (cp.expires_at is None or cp.expires_at > now)
        ]
        if not matches:
            return None
        # Return the most recent checkpoint for this run
        return max(matches, key=lambda cp: cp.created_at)

    async def list_by_session(self, session_id: str) -> list[GraphCheckpoint]:
        now = datetime.now(timezone.utc)
        return [
            cp
            for cp in self._store.values()
            if cp.session_id == session_id and (cp.expires_at is None or cp.expires_at > now)
        ]

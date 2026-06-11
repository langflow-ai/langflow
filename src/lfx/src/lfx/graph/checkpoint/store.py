"""CheckpointStore contract + in-memory reference implementation (LE-1440).

The in-memory store is the standalone/test default; the durable DB-backed
store lands in LE-1441 behind this same interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.graph.checkpoint.schema import GraphCheckpoint


class CheckpointStore(ABC):
    @abstractmethod
    async def save(self, checkpoint: GraphCheckpoint) -> None: ...

    @abstractmethod
    async def load(self, checkpoint_id: str) -> GraphCheckpoint | None: ...

    @abstractmethod
    async def delete(self, checkpoint_id: str) -> None: ...

    @abstractmethod
    async def load_by_run_id(self, run_id: str) -> GraphCheckpoint | None: ...

    @abstractmethod
    async def list_by_session(self, session_id: str) -> list[GraphCheckpoint]: ...


def _expired(checkpoint: GraphCheckpoint) -> bool:
    return checkpoint.expires_at is not None and checkpoint.expires_at <= datetime.now(timezone.utc)


class InMemoryCheckpointStore(CheckpointStore):
    def __init__(self) -> None:
        self._checkpoints: dict[str, GraphCheckpoint] = {}

    async def save(self, checkpoint: GraphCheckpoint) -> None:
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint

    async def load(self, checkpoint_id: str) -> GraphCheckpoint | None:
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint is None or _expired(checkpoint):
            return None
        return checkpoint

    async def delete(self, checkpoint_id: str) -> None:
        self._checkpoints.pop(checkpoint_id, None)

    async def load_by_run_id(self, run_id: str) -> GraphCheckpoint | None:
        candidates = [cp for cp in self._checkpoints.values() if cp.run_id == run_id and not _expired(cp)]
        if not candidates:
            return None
        return max(candidates, key=lambda cp: cp.created_at)

    async def list_by_session(self, session_id: str) -> list[GraphCheckpoint]:
        return [cp for cp in self._checkpoints.values() if cp.session_id == session_id and not _expired(cp)]


_default_store: InMemoryCheckpointStore | None = None


def default_checkpoint_store() -> InMemoryCheckpointStore:
    """Module-singleton fallback store for standalone lfx (no service registry)."""
    global _default_store  # noqa: PLW0603
    if _default_store is None:
        _default_store = InMemoryCheckpointStore()
    return _default_store

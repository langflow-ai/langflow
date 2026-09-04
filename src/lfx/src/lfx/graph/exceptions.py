"""Graph-level control-flow exceptions."""

from __future__ import annotations

from typing import Any


class GraphPausedException(Exception):  # noqa: N818
    """Raised when a run suspends at a safe boundary after persisting a checkpoint.

    This is control flow, not a failure: callers must let it propagate unwrapped
    past generic error handlers so the run is finalized as suspended, never failed.
    """

    def __init__(self, checkpoint_id: str, reason: str, data: dict[str, Any] | None = None) -> None:
        self.checkpoint_id = checkpoint_id
        self.reason = reason
        self.data = data or {}
        super().__init__(f"Graph paused ({reason}); checkpoint {checkpoint_id}")

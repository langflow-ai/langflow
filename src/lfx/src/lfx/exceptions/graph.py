"""Graph execution exceptions."""

from __future__ import annotations

from typing import Any


class GraphPausedException(Exception):
    """Raised when a graph execution is paused at a layer boundary.

    The checkpoint_id can be used to resume execution later.
    """

    def __init__(self, checkpoint_id: str, reason: str, data: dict[str, Any] | None = None) -> None:
        self.checkpoint_id = checkpoint_id
        self.reason = reason
        self.data = data or {}
        super().__init__(f"Graph paused: {reason} (checkpoint={checkpoint_id})")

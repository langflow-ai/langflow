"""Graph mutation event system for comprehensive state tracking.

This module provides the event infrastructure for tracking all graph state changes.
Events are emitted before and after mutations, allowing observers to track
the complete evolution of graph execution state.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = ["GraphMutationEvent", "GraphObserver"]


@dataclass
class GraphMutationEvent:
    """Event emitted when graph state changes.

    Events are serializable for replay and contain complete before/after state.
    """

    event_type: str  # Event type (e.g., "queue_extended", "dependency_added")
    vertex_id: str | None  # Vertex that triggered change (None for graph-level ops)

    # Complete state snapshots
    state_before: dict[str, Any]  # State before mutation
    state_after: dict[str, Any]  # State after mutation

    # Structured description of what changed
    changes: dict[str, Any]  # Added/removed items, size changes, etc.

    # Graph context at mutation time
    graph_snapshot: dict[str, Any]  # Complete graph state

    # Temporal tracking
    step: int  # Global mutation counter

    # Additional context
    metadata: dict[str, Any] = field(default_factory=dict)

    # Timing (before or after mutation)
    timing: str = "after"  # "before" or "after"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for replay/storage."""
        return {
            "event_type": self.event_type,
            "vertex_id": self.vertex_id,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "changes": self.changes,
            "graph_snapshot": self.graph_snapshot,
            "step": self.step,
            "metadata": self.metadata,
            "timing": self.timing,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphMutationEvent:
        """Deserialize from dictionary."""
        return cls(
            event_type=data["event_type"],
            vertex_id=data.get("vertex_id"),
            state_before=data["state_before"],
            state_after=data["state_after"],
            changes=data["changes"],
            graph_snapshot=data["graph_snapshot"],
            step=data["step"],
            metadata=data.get("metadata", {}),
            timing=data.get("timing", "after"),
        )


# Observer type: async function that receives events
GraphObserver = Callable[[GraphMutationEvent], Awaitable[None]]

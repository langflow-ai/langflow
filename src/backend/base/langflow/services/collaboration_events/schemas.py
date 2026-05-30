from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True)
class CollaborationEvent:
    """Opaque collaboration event stored in the cross-worker backplane."""

    id: str
    flow_id: UUID
    created_at: float
    type: str
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CollaborationPollCursor:
    """Per-worker poll position for a flow's collaboration event stream."""

    created_at: float = 0.0
    event_id: str = ""

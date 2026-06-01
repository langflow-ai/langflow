from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Literal

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


@dataclass(frozen=True)
class CollaborationSelectionTarget:
    kind: Literal["node", "edge"]
    id: str


@dataclass(frozen=True)
class CollaborationUserSelection:
    user_id: UUID
    selected: CollaborationSelectionTarget | None = None


@dataclass(frozen=True)
class CollaborationPresenceConnectionUser:
    user_id: UUID
    username: str
    profile_image: str | None = None
    selected: CollaborationSelectionTarget | None = None


@dataclass(frozen=True)
class CollaborationPresenceChange:
    joined: CollaborationPresenceConnectionUser | None = None
    left_user_id: UUID | None = None
    selection_updated: CollaborationUserSelection | None = None

    def __post_init__(self) -> None:
        changes = (self.joined, self.left_user_id, self.selection_updated)
        if sum(change is not None for change in changes) != 1:
            msg = "CollaborationPresenceChange requires exactly one change field"
            raise ValueError(msg)


@dataclass(frozen=True)
class CollaborationPresenceSnapshot:
    users: list[CollaborationPresenceConnectionUser]


UNSET: Final = object()

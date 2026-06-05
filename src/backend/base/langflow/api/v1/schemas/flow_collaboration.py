"""WebSocket message schemas for flow collaboration."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from langflow.services.collaboration_events.schemas import CollaborationSelectionTarget


class CollaborationPresenceUser(BaseModel):
    user_id: UUID
    username: str
    profile_image: str | None = None
    selected: CollaborationSelectionTarget | None = None


class CollaborationSessionStartMessage(BaseModel):
    type: Literal["session.start"]


class CollaborationSessionReadyMessage(BaseModel):
    type: Literal["session.ready"] = "session.ready"
    connection_id: UUID
    flow_id: UUID
    current_revision: int


class CollaborationOperationSubmitMessage(BaseModel):
    type: Literal["operation.submit"]
    request_id: str
    base_revision: int
    operations: list[dict[str, Any]]


class CollaborationOperationAcceptedMessage(BaseModel):
    type: Literal["operation.accepted"] = "operation.accepted"
    request_id: str | None = None
    flow_id: UUID
    revision: int
    actor_user_id: UUID
    forward_ops: list[dict[str, Any]]
    created_at: datetime


class CollaborationOperationRejectedMessage(BaseModel):
    type: Literal["operation.rejected"] = "operation.rejected"
    request_id: str | None = None
    status: int
    detail: str
    current_revision: int | None = None


class CollaborationPresenceSnapshotMessage(BaseModel):
    type: Literal["presence.snapshot"] = "presence.snapshot"
    users: list[CollaborationPresenceUser]


class CollaborationPresenceJoinedMessage(BaseModel):
    type: Literal["presence.joined"] = "presence.joined"
    user: CollaborationPresenceUser


class CollaborationPresenceLeftMessage(BaseModel):
    type: Literal["presence.left"] = "presence.left"
    user_id: UUID


class CollaborationUserSelection(BaseModel):
    # Use the collaboration event service schema as the shared selection contract.
    # If the websocket API diverges later, introduce a dedicated API model here.
    user_id: UUID
    selected: CollaborationSelectionTarget | None = None


class CollaborationSelectionUpdateMessage(BaseModel):
    type: Literal["selection.update"]
    selected: CollaborationSelectionTarget | None = None


class CollaborationSelectionUpdatedMessage(BaseModel):
    type: Literal["selection.updated"] = "selection.updated"
    user_id: UUID
    selected: CollaborationSelectionTarget | None = None


class CollaborationHeartbeatPingMessage(BaseModel):
    type: Literal["heartbeat.ping"] = "heartbeat.ping"


class CollaborationHeartbeatPongMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["heartbeat.pong"]


class CollaborationOperationBroadcastMessage(BaseModel):
    """Accepted operation broadcast to peers (not echoed to origin)."""

    type: Literal["operation.broadcast"] = "operation.broadcast"
    flow_id: UUID
    revision: int
    actor_user_id: UUID
    forward_ops: list[dict[str, Any]]
    created_at: datetime


class CollaborationOperationAcceptedEventPayload(BaseModel):
    """Typed payload stored in the collaboration event backplane."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str
    revision: StrictInt
    actor_user_id: UUID
    forward_ops: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class CollaborationPresenceJoinedEventPayload(BaseModel):
    """Typed presence.joined payload stored in the collaboration event backplane."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str
    user: CollaborationPresenceUser


class CollaborationPresenceLeftEventPayload(BaseModel):
    """Typed presence.left payload stored in the collaboration event backplane."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str
    user_id: UUID


class CollaborationSelectionUpdatedEventPayload(BaseModel):
    """Typed selection.updated payload stored in the collaboration event backplane."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str
    user_id: UUID
    selected: CollaborationSelectionTarget | None = None


class CollaborationOperationAcceptedBackplaneEvent(BaseModel):
    """Typed accepted-operation event consumed from the collaboration backplane."""

    type: Literal["operation.accepted"]
    payload: CollaborationOperationAcceptedEventPayload


class CollaborationPresenceJoinedBackplaneEvent(BaseModel):
    type: Literal["presence.joined"]
    payload: CollaborationPresenceJoinedEventPayload


class CollaborationPresenceLeftBackplaneEvent(BaseModel):
    type: Literal["presence.left"]
    payload: CollaborationPresenceLeftEventPayload


class CollaborationSelectionUpdatedBackplaneEvent(BaseModel):
    type: Literal["selection.updated"]
    payload: CollaborationSelectionUpdatedEventPayload


CollaborationBackplaneEvent = (
    CollaborationOperationAcceptedBackplaneEvent
    | CollaborationPresenceJoinedBackplaneEvent
    | CollaborationPresenceLeftBackplaneEvent
    | CollaborationSelectionUpdatedBackplaneEvent
)


class UnsupportedCollaborationBackplaneEventError(ValueError):
    """Raised when the collaboration manager receives an unknown backplane event type."""


def parse_collaboration_backplane_event(event_type: str, payload: dict[str, Any]) -> CollaborationBackplaneEvent:
    """Parse the opaque event-service payload into a typed collaboration event."""
    event = {"type": event_type, "payload": payload}
    if event_type == "operation.accepted":
        return CollaborationOperationAcceptedBackplaneEvent.model_validate(event)
    if event_type == "presence.joined":
        return CollaborationPresenceJoinedBackplaneEvent.model_validate(event)
    if event_type == "presence.left":
        return CollaborationPresenceLeftBackplaneEvent.model_validate(event)
    if event_type == "selection.updated":
        return CollaborationSelectionUpdatedBackplaneEvent.model_validate(event)
    msg = f"Unsupported collaboration backplane event type: {event_type!r}"
    raise UnsupportedCollaborationBackplaneEventError(msg)


class CollaborationUnknownMessageError(BaseModel):
    type: Literal["message.error"] = "message.error"
    detail: str = "Unknown message type"


CollaborationClientMessage = (
    CollaborationSessionStartMessage
    | CollaborationOperationSubmitMessage
    | CollaborationSelectionUpdateMessage
    | CollaborationHeartbeatPongMessage
)

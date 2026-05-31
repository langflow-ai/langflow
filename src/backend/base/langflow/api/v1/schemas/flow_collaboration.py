"""WebSocket message schemas for flow collaboration."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from lfx.services.flow_operations.ops import FlowOperationActorDelegate
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt


class CollaborationPresenceUser(BaseModel):
    user_id: str
    username: str
    profile_image: str | None = None


class CollaborationSessionStartMessage(BaseModel):
    type: Literal["session.start"]


class CollaborationSessionReadyMessage(BaseModel):
    type: Literal["session.ready"] = "session.ready"
    connection_id: str
    flow_id: UUID
    current_revision: int
    users: list[CollaborationPresenceUser]


class CollaborationSessionErrorMessage(BaseModel):
    type: Literal["session.error"] = "session.error"
    code: str
    detail: str


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
    actor_delegate: FlowOperationActorDelegate
    forward_ops: list[dict[str, Any]]
    created_at: datetime


class CollaborationOperationRejectedMessage(BaseModel):
    type: Literal["operation.rejected"] = "operation.rejected"
    request_id: str | None = None
    status: int
    detail: str
    current_revision: int | None = None


class CollaborationPresenceUpdatedMessage(BaseModel):
    type: Literal["presence.updated"] = "presence.updated"
    users: list[CollaborationPresenceUser]


class CollaborationOperationBroadcastMessage(BaseModel):
    """Accepted operation broadcast to peers (not echoed to origin)."""

    type: Literal["operation.broadcast"] = "operation.broadcast"
    flow_id: UUID
    revision: int
    actor_user_id: UUID
    actor_delegate: FlowOperationActorDelegate
    forward_ops: list[dict[str, Any]]
    created_at: datetime


class CollaborationOperationAcceptedEventPayload(BaseModel):
    """Typed payload stored in the collaboration event backplane."""

    model_config = ConfigDict(extra="forbid")

    revision: StrictInt
    actor_user_id: UUID
    actor_delegate: FlowOperationActorDelegate = FlowOperationActorDelegate.SELF
    forward_ops: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    origin_connection_id: str | None = None


class CollaborationPresenceEventPayload(BaseModel):
    """Typed presence roster payload stored in the collaboration event backplane."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str
    published_at: StrictFloat
    users: list[CollaborationPresenceUser] = Field(default_factory=list)


class CollaborationOperationAcceptedBackplaneEvent(BaseModel):
    """Typed accepted-operation event consumed from the collaboration backplane."""

    type: Literal["operation.accepted"]
    payload: CollaborationOperationAcceptedEventPayload


class CollaborationPresenceUpdatedBackplaneEvent(BaseModel):
    """Typed presence event consumed from the collaboration backplane."""

    type: Literal["presence.updated"]
    payload: CollaborationPresenceEventPayload


CollaborationBackplaneEvent = CollaborationOperationAcceptedBackplaneEvent | CollaborationPresenceUpdatedBackplaneEvent


class UnsupportedCollaborationBackplaneEventError(ValueError):
    """Raised when the collaboration manager receives an unknown backplane event type."""


def parse_collaboration_backplane_event(event_type: str, payload: dict[str, Any]) -> CollaborationBackplaneEvent:
    """Parse the opaque event-service payload into a typed collaboration event."""
    event = {"type": event_type, "payload": payload}
    if event_type == "operation.accepted":
        return CollaborationOperationAcceptedBackplaneEvent.model_validate(event)
    if event_type == "presence.updated":
        return CollaborationPresenceUpdatedBackplaneEvent.model_validate(event)
    msg = f"Unsupported collaboration backplane event type: {event_type!r}"
    raise UnsupportedCollaborationBackplaneEventError(msg)


class CollaborationUnknownMessageError(BaseModel):
    type: Literal["message.error"] = "message.error"
    detail: str = "Unknown message type"


CollaborationClientMessage = CollaborationSessionStartMessage | CollaborationOperationSubmitMessage

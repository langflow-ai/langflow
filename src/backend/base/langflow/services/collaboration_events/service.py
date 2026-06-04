from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from langflow.services.base import Service
from langflow.services.collaboration_events.schemas import UNSET, CollaborationSelectionTarget

if TYPE_CHECKING:
    from uuid import UUID

    from langflow.services.collaboration_events.schemas import (
        CollaborationEvent,
        CollaborationPollCursor,
        CollaborationPresenceChange,
        CollaborationPresenceChangeEnvelope,
        CollaborationPresenceSnapshot,
    )


class CollaborationEventService(Service, ABC):
    """Cross-worker event backplane for collaborative flow editing.

    Publishes opaque events scoped by ``flow_id``. Workers poll events for flows
    they are actively serving and fan them out to local WebSocket rooms.

    Ephemeral presence and per-connection selection state live in the same store
    and are authoritative for bootstrap/resync snapshots.
    """

    name = "collaboration_events_service"

    @abstractmethod
    async def publish(self, flow_id: UUID, event_type: str, payload: dict) -> CollaborationEvent:
        """Push an event for cross-worker fanout."""

    @abstractmethod
    async def poll(
        self,
        flow_id: UUID,
        *,
        cursor: CollaborationPollCursor | None = None,
        limit: int | None = None,
    ) -> tuple[list[CollaborationEvent], CollaborationPollCursor]:
        """Return events after ``cursor`` and the updated poll cursor."""

    @abstractmethod
    async def cleanup(self) -> None:
        """Force-evict expired events and presence rows. Useful for tests and ops scripts."""

    @abstractmethod
    async def add_connection(
        self,
        *,
        flow_id: UUID,
        user_id: UUID,
        connection_id: UUID,
        username: str,
        profile_image: str | None,
    ) -> CollaborationPresenceChange | None:
        """Create or replace one active connection row."""

    @abstractmethod
    async def update_connection(
        self,
        *,
        connection_id: UUID,
        selected: CollaborationSelectionTarget | None | object = UNSET,
    ) -> CollaborationPresenceChange | None:
        """Refresh the connection TTL and optionally update its selection columns."""

    @abstractmethod
    async def remove_connection(
        self,
        *,
        connection_id: UUID,
    ) -> CollaborationPresenceChange | None:
        """Remove one active connection row."""

    @abstractmethod
    async def remove_connections(self, connection_ids: list[UUID]) -> list[CollaborationPresenceChangeEnvelope]:
        """Remove active connection rows and return user-visible presence changes keyed by flow id."""

    @abstractmethod
    async def list_users(self, flow_ids: list[UUID]) -> dict[UUID, CollaborationPresenceSnapshot]:
        """Return active deduped users plus effective per-user selections keyed by flow id."""

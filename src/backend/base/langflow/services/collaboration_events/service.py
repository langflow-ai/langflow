from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from langflow.services.base import Service

if TYPE_CHECKING:
    from uuid import UUID

    from langflow.services.collaboration_events.schemas import CollaborationEvent, CollaborationPollCursor


class CollaborationEventService(Service, ABC):
    """Cross-worker event backplane for collaborative flow editing.

    Publishes opaque events scoped by ``flow_id``. Workers poll events for flows
    they are actively serving and fan them out to local WebSocket rooms.
    """

    name = "collaboration_events_service"

    @abstractmethod
    def publish(self, flow_id: UUID, event_type: str, payload: dict) -> CollaborationEvent:
        """Persist an event for cross-worker fanout."""

    @abstractmethod
    def poll(
        self,
        flow_id: UUID,
        *,
        cursor: CollaborationPollCursor | None = None,
        limit: int | None = None,
    ) -> tuple[list[CollaborationEvent], CollaborationPollCursor]:
        """Return events after ``cursor`` and the updated poll cursor."""

    @abstractmethod
    def cleanup(self) -> None:
        """Force-evict expired events. Useful for tests and ops scripts."""

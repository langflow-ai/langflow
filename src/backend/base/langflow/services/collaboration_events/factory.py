from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.collaboration_events.sqlite import SQLiteCollaborationEventService
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

    from langflow.services.collaboration_events.service import CollaborationEventService


class CollaborationEventServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(SQLiteCollaborationEventService)

    @override
    def create(self, settings_service: SettingsService) -> CollaborationEventService:
        settings = settings_service.settings
        return SQLiteCollaborationEventService(
            cache_dir=settings.cache_dir,
            presence_ttl_seconds=settings.collaboration_connection_ttl,
        )

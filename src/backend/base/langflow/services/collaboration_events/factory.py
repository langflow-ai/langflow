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
        return SQLiteCollaborationEventService(cache_dir=settings_service.settings.cache_dir)

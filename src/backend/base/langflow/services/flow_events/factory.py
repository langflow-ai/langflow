from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.flow_events.service import FlowEventsService

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class FlowEventsServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(FlowEventsService)

    @override
    def create(self, settings_service: SettingsService):
        return FlowEventsService(cache_dir=settings_service.settings.cache_dir)

from typing import TYPE_CHECKING

from langflow.services.event_bus.service import EventBusService
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class EventBusServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(EventBusService)

    def create(self, settings_service: "SettingsService"):
        return EventBusService(settings_service)

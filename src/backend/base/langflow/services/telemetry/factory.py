from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.telemetry.service import TelemetryService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class TelemetryServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(TelemetryService)

    def create(self, settings_service: "SettingsService"):
        return TelemetryService(settings_service)

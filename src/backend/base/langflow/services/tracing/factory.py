from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.tracing.service import TracingService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService
    from langflow.services.monitor.service import MonitorService


class TracingServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(TracingService)

    def create(self, settings_service: "SettingsService", monitor_service: "MonitorService"):
        return TracingService(settings_service, monitor_service)

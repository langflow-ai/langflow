from typing import TYPE_CHECKING

from langflow.services.base import Service

if TYPE_CHECKING:
    from langflow.services.monitor.service import MonitorService
    from langflow.services.settings.service import SettingsService


class TracingService(Service):
    name = "tracing_service"

    def __init__(self, settings_service: "SettingsService", monitor_service: "MonitorService"):
        self.settings_service = settings_service
        self.monitor_service = monitor_service

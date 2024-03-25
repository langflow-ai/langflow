from langflow_base.services.factory import ServiceFactory
from langflow_base.services.monitor.service import MonitorService
from langflow_base.services.settings.service import SettingsService


class MonitorServiceFactory(ServiceFactory):
    name = "monitor_service"

    def __init__(self):
        super().__init__(MonitorService)

    def create(self, settings_service: SettingsService):
        return self.service_class(settings_service)

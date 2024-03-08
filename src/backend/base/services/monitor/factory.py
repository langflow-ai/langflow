from langflow.services.factory import ServiceFactory
from langflow.services.monitor.service import MonitorService


class MonitorServiceFactory(ServiceFactory):
    name = "monitor_service"

    def __init__(self):
        super().__init__(MonitorService)

    def create(self, settings_service):
        return self.service_class(settings_service)

from langflow.services.event_bus.service import EventBusService
from langflow.services.factory import ServiceFactory


class EventBusServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(EventBusService)

    def create(self):
        return EventBusService()

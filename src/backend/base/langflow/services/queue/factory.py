from langflow.services.base import Service
from langflow.services.factory import ServiceFactory
from langflow.services.queue.service import QueueService


class QueueServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(QueueService)

    def create(self) -> Service:
        return QueueService()

"""Factory for creating SchedulerService instances."""

from langflow.services.factory import ServiceFactory
from langflow.services.scheduler.service import SchedulerService


class SchedulerServiceFactory(ServiceFactory):
    """Factory for creating SchedulerService instances."""

    def __init__(self):
        super().__init__(SchedulerService)
        self._instance = None

    def create(self):
        if self._instance is None:
            self._instance = SchedulerService()
        return self._instance

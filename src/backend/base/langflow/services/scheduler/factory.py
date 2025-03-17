"""Factory for the scheduler service."""

from typing import Any

from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.scheduler.service import SchedulerService, scheduler_service
from langflow.services.schema import ServiceType


class SchedulerServiceFactory(ServiceFactory):
    """Factory for the scheduler service."""

    name = ServiceType.SCHEDULER_SERVICE

    def __init__(self):
        """Initialize the factory."""
        super().__init__(SchedulerService)

    @override
    def create(self) -> Any:
        """Create a new instance of the scheduler service."""
        return scheduler_service

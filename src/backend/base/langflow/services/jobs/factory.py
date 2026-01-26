"""Factory for creating JobService instances."""

from langflow.services.factory import ServiceFactory
from langflow.services.jobs.service import JobService


class JobServiceFactory(ServiceFactory):
    """Factory for creating JobService instances."""

    def __init__(self):
        super().__init__(JobService)

    def create(self):
        """Create a JobService instance.

        Returns:
            JobService instance
        """
        return JobService()

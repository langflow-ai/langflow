"""Factory for creating JobService instances."""

from langflow.services.factory import ServiceFactory
from langflow.services.jobs.service import JobService


class JobServiceFactory(ServiceFactory):
    """Factory for creating JobService instances."""

    def __init__(self):
        super().__init__(JobService)
        self._instance = None

    def create(self):
        """Create a JobService instance.

        Returns:
            JobService instance
        """
        if self._instance is None:
            self._instance = JobService()
        return self._instance

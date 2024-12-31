from langflow.services.database.service import DatabaseService
from langflow.services.factory import ServiceFactory
from langflow.services.jobs.service import JobsService
from langflow.services.settings.service import SettingsService


class JobsServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(JobsService)

    def create(self, settings_service: SettingsService, database_service: DatabaseService) -> JobsService:
        """Create a new JobsService instance with the required dependencies."""
        return JobsService(settings_service=settings_service, database_service=database_service)

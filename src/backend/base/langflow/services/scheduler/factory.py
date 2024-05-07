from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.scheduler.service import SchedulerService

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService


class SchedulerServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(SchedulerService)

    def create(self, database_service: "DatabaseService"):
        return SchedulerService(database_service)

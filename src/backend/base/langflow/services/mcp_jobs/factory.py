from langflow.services.base import Service
from langflow.services.factory import ServiceFactory
from langflow.services.mcp_jobs.service import MCPJobExecutorService


class MCPJobExecutorServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(MCPJobExecutorService)

    def create(self) -> Service:
        return MCPJobExecutorService()

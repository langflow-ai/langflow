from langflow.services.factory import ServiceFactory
from langflow.services.flow_cache.service import FlowCacheService


class FlowCacheServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(FlowCacheService)

    def create(self):
        return FlowCacheService()

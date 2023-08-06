from langflow.services.cache.manager import CacheManager
from langflow.services.factory import ServiceFactory


class CacheManagerFactory(ServiceFactory):
    def __init__(self):
        super().__init__(CacheManager)

    def create(self, settings_service):
        # Here you would have logic to create and configure a CacheManager
        return CacheManager()

from typing import TYPE_CHECKING
from langflow.services.session.manager import SessionManager
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.cache.manager import BaseCacheManager


class SessionManagerFactory(ServiceFactory):
    def __init__(self):
        super().__init__(SessionManager)

    def create(self, cache_manager: "BaseCacheManager"):
        return SessionManager(cache_manager)

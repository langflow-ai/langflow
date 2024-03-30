from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.socket.service import SocketIOService

if TYPE_CHECKING:
    from langflow.services.cache.service import CacheService


class SocketIOFactory(ServiceFactory):
    def __init__(self):
        super().__init__(
            service_class=SocketIOService,
        )

    def create(self, cache_service: "CacheService"):
        return SocketIOService(cache_service)

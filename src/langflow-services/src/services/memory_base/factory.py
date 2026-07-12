"""Factory for creating MemoryBaseService instances."""

from services.factory import ServiceFactory
from services.memory_base.service import MemoryBaseService


class MemoryBaseServiceFactory(ServiceFactory):
    """Factory for creating MemoryBaseService instances."""

    def __init__(self):
        super().__init__(MemoryBaseService)

    def create(self):
        return MemoryBaseService()

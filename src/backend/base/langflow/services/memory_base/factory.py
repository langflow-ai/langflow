"""Factory for creating MemoryBaseService instances."""

from langflow.services.factory import ServiceFactory
from langflow.services.memory_base.service import MemoryBaseService


class MemoryBaseServiceFactory(ServiceFactory):
    """Factory for creating MemoryBaseService instances."""

    def __init__(self):
        super().__init__(MemoryBaseService)

    def create(self):
        return MemoryBaseService()

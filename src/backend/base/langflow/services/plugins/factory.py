from __future__ import annotations

from langflow.services.factory import ServiceFactory
from langflow.services.plugins.service import PluginService


class PluginServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(PluginService)

    def create(self):
        return PluginService()

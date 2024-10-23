from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.store.service import StoreService

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class StoreServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(StoreService)

    def create(self, settings_service: SettingsService):
        return StoreService(settings_service)

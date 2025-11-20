from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.store.service import DisabledStoreService, StoreService

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class StoreServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(StoreService)

    @override
    def create(self, settings_service: SettingsService):
        if not settings_service.settings.store:
            return DisabledStoreService(settings_service)
        return StoreService(settings_service)

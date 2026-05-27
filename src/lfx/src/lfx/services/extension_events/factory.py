from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.extension_events.service import ExtensionEventsService
from lfx.services.factory import ServiceFactory

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class ExtensionEventsServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__()
        self.service_class = ExtensionEventsService

    def create(self, settings_service: SettingsService | None = None, **_kwargs) -> ExtensionEventsService:
        cache_dir = None
        if settings_service is not None:
            cache_dir = getattr(settings_service.settings, "cache_dir", None)
        return ExtensionEventsService(cache_dir=cache_dir)

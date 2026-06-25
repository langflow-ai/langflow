"""Factory for the capability service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.capability.service import CapabilityService
from lfx.services.factory import ServiceFactory
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class CapabilityServiceFactory(ServiceFactory):
    """Factory for creating CapabilityService instances."""

    def __init__(self) -> None:
        super().__init__()
        self.service_class = CapabilityService
        self.dependencies = [ServiceType.SETTINGS_SERVICE]

    def create(self, settings_service: SettingsService) -> CapabilityService:
        return CapabilityService(settings_service=settings_service)

"""Factory for the executor service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.executor.service import ExecutorService
from lfx.services.factory import ServiceFactory
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.capability import CapabilityService
    from lfx.services.settings.service import SettingsService


class ExecutorServiceFactory(ServiceFactory):
    """Factory for creating ExecutorService instances."""

    def __init__(self) -> None:
        super().__init__()
        self.service_class = ExecutorService
        self.dependencies = [ServiceType.SETTINGS_SERVICE, ServiceType.CAPABILITY_SERVICE]

    def create(self, settings_service: SettingsService, capability_service: CapabilityService) -> ExecutorService:
        return ExecutorService(settings_service=settings_service, capability_service=capability_service)

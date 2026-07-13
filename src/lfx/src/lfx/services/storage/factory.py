"""Factory for the lean local storage service used by bare lfx."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from lfx.services.factory import ServiceFactory
from lfx.services.schema import ServiceType
from lfx.services.storage.local import LocalStorageService

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class StorageServiceFactory(ServiceFactory):
    """Registers ``LocalStorageService`` as the no-deps default storage backend.

    This is the lean default for bare lfx: it depends only on the settings
    service (always available) so any file-backed component has a real storage
    service instead of ``None``. A heavier backend (e.g. langflow) overrides it
    through the same service manager by registering its own storage factory or
    service class.
    """

    def __init__(self) -> None:
        super().__init__()
        self.service_class = LocalStorageService
        self.dependencies = [ServiceType.SETTINGS_SERVICE]

    @override
    def create(self, settings_service: SettingsService) -> LocalStorageService:
        # Bare lfx has no session service. LocalStorageService only needs the
        # settings service for its data_dir; session_service is stored but never
        # used by any file operation, so passing None here is safe.
        return LocalStorageService(session_service=None, settings_service=settings_service)

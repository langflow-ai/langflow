"""Storage service for langflow - redirects to lfx implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.base import Service

# Re-export from lfx
from lfx.services.storage.service import StorageService as LfxStorageService

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

    from langflow.services.session.service import SessionService


class StorageService(Service, LfxStorageService):
    """Storage service that extends langflow's Service and lfx's StorageService.
    
    This provides compatibility with langflow's service architecture while
    using the lfx StorageService implementation.
    """
    name = "storage_service"

    def __init__(self, session_service: SessionService, settings_service: SettingsService):
        """Initialize the storage service with session and settings services."""
        # Initialize Service first
        Service.__init__(self)
        # Initialize lfx StorageService with services (it now takes session_service and settings_service)
        LfxStorageService.__init__(self, session_service=session_service, settings_service=settings_service)
        # LfxStorageService already sets self.settings_service, self.session_service, and self.data_dir
        # LfxStorageService already calls set_ready() internally
        self.set_ready()

    def set_ready(self) -> None:
        """Mark the service as ready, syncing both parent classes."""
        Service.set_ready(self)
        self._ready = True

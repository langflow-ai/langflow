"""Storage service for langflow - redirects to lfx implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Re-export from lfx
from lfx.services.storage.service import StorageService as LfxStorageService

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

    from langflow.services.session.service import SessionService


class StorageService(LfxStorageService):
    """Storage service that extends lfx's StorageService.

    This provides compatibility with langflow's service architecture while
    using the lfx StorageService implementation.
    """

    name = "storage_service"

    def __init__(self, session_service: SessionService, settings_service: SettingsService):
        """Initialize the storage service with session and settings services."""
        # Initialize lfx StorageService (which already inherits from Service)
        super().__init__(session_service=session_service, settings_service=settings_service)
        # LfxStorageService already sets self.settings_service, self.session_service, and self.data_dir
        # LfxStorageService already calls set_ready() internally

"""Sandbox service factory for dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class SandboxServiceFactory(ServiceFactory):
    """Factory for creating SandboxService instances."""

    def __init__(self):
        from langflow.services.sandbox.service import SandboxService
        super().__init__(SandboxService)

    @override
    def create(self, settings_service: SettingsService):
        """Create a new SandboxService instance."""
        from langflow.services.sandbox.service import SandboxService
        return SandboxService(settings_service=settings_service)

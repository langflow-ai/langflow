"""Factory for BackgroundExecutionService."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class BackgroundExecutionServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(BackgroundExecutionService)

    @override
    def create(self, settings_service: SettingsService):
        return BackgroundExecutionService(settings_service)

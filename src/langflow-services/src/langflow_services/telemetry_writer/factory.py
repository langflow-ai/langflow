from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow_services.factory import ServiceFactory
from langflow_services.telemetry_writer.service import TelemetryWriterService

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class TelemetryWriterServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(TelemetryWriterService)

    @override
    def create(self, settings_service: SettingsService):
        return TelemetryWriterService(settings_service)

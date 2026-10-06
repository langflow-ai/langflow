from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from langflow.services.base import Service
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from langflow.services.telemetry.run_event_store import append_run_event

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

    from langflow.services.telemetry.schema import RunPayload


class TelemetryService(Service):
    """Application observability and the local completed-run event boundary.

    Remote analytics transport was removed. The service remains registered so
    existing application metrics and tracing continue to share the OpenTelemetry
    providers, and so enterprise consumers can drain completed runs locally.
    """

    name = "telemetry_service"

    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.settings_service = settings_service
        self.ot = OpenTelemetry(prometheus_enabled=settings_service.settings.prometheus_enabled)
        self.running = False
        self._stopping = False

    async def log_package_run(self, payload: RunPayload) -> None:
        """Record a completed run for local consumers without network I/O."""
        append_run_event(payload)

    def start(self) -> None:
        """Retain the lifecycle hook while keeping startup network-free."""
        self.running = True
        self._stopping = False

    async def flush(self) -> None:
        """Retained as an inert compatibility hook for service lifecycle callers."""

    async def stop(self) -> None:
        """Stop lifecycle state; providers close in ``teardown``."""
        self._stopping = True
        self.running = False

    async def teardown(self) -> None:
        await self.stop()
        # Off the event loop: final provider export may block on the network.
        await asyncio.to_thread(self.ot.shutdown)

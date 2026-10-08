"""Compatibility telemetry service for lfx.

Product analytics were removed from LFX. The service and its logging methods
remain as inert compatibility hooks for hosts and extensions that still resolve
the historical ``telemetry_service`` entry point. Operational tracing and
metrics use the OpenTelemetry APIs in :mod:`lfx.observability` instead.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.services.telemetry.base import BaseTelemetryService

if TYPE_CHECKING:
    from pydantic import BaseModel


class TelemetryService(BaseTelemetryService):
    """No-op implementation retained for the historical LFX service contract.

    The legacy ``do_not_track`` value is accepted for compatibility. Both
    ``True`` and ``False`` are currently ignored and reserved for a future
    telemetry integration.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        do_not_track: bool | None = None,
    ) -> None:
        """Accept legacy transport options without using them.

        ``base_url`` and ``do_not_track`` are intentionally retained so older
        service registrations and integrations continue to instantiate. No
        value, including an explicitly configured URL or ``False`` for
        ``do_not_track``, can enable product analytics.
        """
        super().__init__()
        self.base_url = base_url
        self.do_not_track = bool(do_not_track) if do_not_track is not None else False
        self._running = False
        self._stopping = False
        self._start_time = datetime.now(timezone.utc)
        self.set_ready()

    @property
    def name(self) -> str:
        return "telemetry_service"

    def start(self) -> None:
        """Retain the lifecycle hook; no worker or network client is started."""
        self._running = False

    async def stop(self) -> None:
        """Retain the lifecycle hook; there is no pending product telemetry."""
        self._running = False
        self._stopping = False

    async def flush(self) -> None:
        """Retain the flush hook as an inert operation."""

    async def teardown(self) -> None:
        await self.stop()

    async def send_telemetry_data(self, payload: BaseModel, path: str | None = None) -> None:
        """Discard the historical outbound payload without any side effects."""

    async def log_package_run(self, payload: BaseModel) -> None:
        """Compatibility hook for package run events."""

    async def log_integration_action(self, payload: BaseModel) -> None:
        """Compatibility hook for integration action events."""

    async def log_package_shutdown(self) -> None:
        """Compatibility hook for package shutdown events."""

    async def log_package_version(self) -> None:
        """Compatibility hook for package version events."""

    async def log_package_playground(self, payload: BaseModel) -> None:
        """Compatibility hook for playground events."""

    async def log_package_component(self, payload: BaseModel) -> None:
        """Compatibility hook for component events."""

    async def log_exception(self, exc: Exception, context: str) -> None:
        """Compatibility hook for exception events."""

    async def log_mcp_tool(self, payload: BaseModel) -> None:
        """Compatibility hook for MCP tool events."""

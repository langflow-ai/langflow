"""Lightweight telemetry service for LFX package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.telemetry.base import BaseTelemetryService

if TYPE_CHECKING:
    from pydantic import BaseModel


class TelemetryService(BaseTelemetryService):
    """Minimal telemetry service implementation for LFX.

    This is a lightweight implementation that logs telemetry events
    but does not send data to any external service. For full telemetry
    functionality, use the Langflow TelemetryService.
    """

    def __init__(self):
        """Initialize the telemetry service with do-not-track enabled."""
        super().__init__()
        self.do_not_track = True  # Minimal implementation never sends data
        self.set_ready()

    @property
    def name(self) -> str:
        """Service name identifier.

        Returns:
            str: The service name.
        """
        return "telemetry_service"

    async def send_telemetry_data(self, payload: BaseModel, path: str | None = None) -> None:  # noqa: ARG002
        """Log telemetry data (minimal implementation - no actual sending).

        Args:
            payload: The telemetry payload
            path: Optional path
        """
        logger.debug(f"Telemetry event (not sent): {path}")

    async def log_package_run(self, payload: BaseModel) -> None:  # noqa: ARG002
        """Log a package run event.

        Args:
            payload: Run payload
        """
        logger.debug("Telemetry: package run")

    async def log_package_shutdown(self) -> None:
        """Log a package shutdown event."""
        logger.debug("Telemetry: package shutdown")

    async def log_package_version(self) -> None:
        """Log the package version."""
        logger.debug("Telemetry: package version")

    async def log_package_playground(self, payload: BaseModel) -> None:  # noqa: ARG002
        """Log a playground interaction.

        Args:
            payload: Playground payload
        """
        logger.debug("Telemetry: playground interaction")

    async def log_package_component(self, payload: BaseModel) -> None:  # noqa: ARG002
        """Log a component usage.

        Args:
            payload: Component payload
        """
        logger.debug("Telemetry: component usage")

    async def log_exception(self, exc: Exception, context: str) -> None:
        """Log an unhandled exception.

        Args:
            exc: The exception
            context: Exception context
        """
        logger.debug(f"Telemetry: exception in {context}: {exc.__class__.__name__}")

    def start(self) -> None:
        """Start the telemetry service (minimal implementation - noop)."""
        logger.debug("Telemetry service started (minimal mode)")

    async def stop(self) -> None:
        """Stop the telemetry service (minimal implementation - noop)."""
        logger.debug("Telemetry service stopped")

    async def flush(self) -> None:
        """Flush pending telemetry (minimal implementation - noop)."""

    async def teardown(self) -> None:
        """Teardown the telemetry service."""
        await self.stop()

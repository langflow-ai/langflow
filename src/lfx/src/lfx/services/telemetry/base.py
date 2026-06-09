"""Abstract base class for telemetry services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from lfx.services.base import Service

if TYPE_CHECKING:
    from pydantic import BaseModel


class BaseTelemetryService(Service, ABC):
    """Abstract base class for telemetry services.

    Defines the minimal interface that all telemetry service implementations
    must provide, whether minimal (LFX) or full-featured (Langflow).
    """

    @abstractmethod
    def __init__(self):
        """Initialize the telemetry service."""
        super().__init__()

    @abstractmethod
    async def send_telemetry_data(self, payload: BaseModel, path: str | None = None) -> None:
        """Send telemetry data to the telemetry backend.

        Args:
            payload: The telemetry payload to send
            path: Optional path to append to the base URL
        """

    @abstractmethod
    async def log_package_run(self, payload: BaseModel) -> None:
        """Log a package run event.

        Args:
            payload: Run payload containing run information
        """

    @abstractmethod
    async def log_package_shutdown(self) -> None:
        """Log a package shutdown event."""

    @abstractmethod
    async def log_package_version(self) -> None:
        """Log the package version information."""

    @abstractmethod
    async def log_package_playground(self, payload: BaseModel) -> None:
        """Log a playground interaction event.

        Args:
            payload: Playground payload containing interaction information
        """

    @abstractmethod
    async def log_package_component(self, payload: BaseModel) -> None:
        """Log a component usage event.

        Args:
            payload: Component payload containing component information
        """

    @abstractmethod
    async def log_exception(self, exc: Exception, context: str) -> None:
        """Log an unhandled exception.

        Args:
            exc: The exception that occurred
            context: Context where exception occurred
        """

    @abstractmethod
    def start(self) -> None:
        """Start the telemetry service."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the telemetry service."""

    @abstractmethod
    async def flush(self) -> None:
        """Flush any pending telemetry data."""

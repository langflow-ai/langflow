"""Lightweight tracing service for lfx package."""

from lfx.services.base import Service


class TracingService(Service):
    """Lightweight tracing service."""

    @property
    def name(self) -> str:
        return "tracing_service"

    def log(self, message: str, **kwargs) -> None:  # noqa: ARG002
        """Log a message with optional metadata."""
        # Lightweight implementation - just log basic info
        from loguru import logger

        logger.debug(f"Trace: {message}")

    async def teardown(self) -> None:
        """Teardown the tracing service."""

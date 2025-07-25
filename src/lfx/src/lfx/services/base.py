"""Base service classes for lfx package."""

from abc import ABC, abstractmethod


class Service(ABC):
    """Base service class."""

    def __init__(self):
        self._ready = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Service name."""

    def set_ready(self) -> None:
        """Mark service as ready."""
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if service is ready."""
        return self._ready

    @abstractmethod
    async def teardown(self) -> None:
        """Teardown the service."""

"""Service interface protocols for lfx package."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import asyncio


class DatabaseServiceProtocol(Protocol):
    """Protocol for database service."""

    @abstractmethod
    def with_session(self) -> Any:
        """Get database session."""
        ...


class StorageServiceProtocol(Protocol):
    """Protocol for storage service."""

    @abstractmethod
    def save(self, data: Any, filename: str) -> str:
        """Save data to storage."""
        ...

    @abstractmethod
    def get_file(self, path: str) -> Any:
        """Get file from storage."""
        ...

    @abstractmethod
    def get_file_paths(self, files: list[str | dict]) -> list[str]:
        """Get file paths from storage."""
        ...

    @abstractmethod
    def build_full_path(self, flow_id: str, file_name: str) -> str:
        """Build the full path of a file in the storage."""
        ...


class SettingsServiceProtocol(Protocol):
    """Protocol for settings service."""

    @property
    @abstractmethod
    def settings(self) -> Any:
        """Get settings object."""
        ...


class VariableServiceProtocol(Protocol):
    """Protocol for variable service."""

    @abstractmethod
    def get_variable(self, name: str, **kwargs) -> Any:
        """Get variable value."""
        ...

    @abstractmethod
    def set_variable(self, name: str, value: Any, **kwargs) -> None:
        """Set variable value."""
        ...


class CacheServiceProtocol(Protocol):
    """Protocol for cache service."""

    @abstractmethod
    def get(self, key: str) -> Any:
        """Get cached value."""
        ...

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set cached value."""
        ...


class ChatServiceProtocol(Protocol):
    """Protocol for chat service."""

    @abstractmethod
    async def get_cache(self, key: str, lock: asyncio.Lock | None = None) -> Any:
        """Get cached value."""
        ...

    @abstractmethod
    async def set_cache(self, key: str, data: Any, lock: asyncio.Lock | None = None) -> bool:
        """Set cached value."""
        ...


class TracingServiceProtocol(Protocol):
    """Protocol for tracing service."""

    @abstractmethod
    def log(self, message: str, **kwargs) -> None:
        """Log tracing information."""
        ...

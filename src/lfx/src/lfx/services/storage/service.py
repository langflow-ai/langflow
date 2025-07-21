"""Base storage service for lfx package."""

from abc import ABC, abstractmethod
from pathlib import Path


class StorageService(ABC):
    """Abstract base class for storage services."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        """Initialize the storage service.

        Args:
            data_dir: Directory path for storing data. Defaults to ~/.lfx/data
        """
        if data_dir is None:
            data_dir = Path.home() / ".lfx" / "data"
        self.data_dir = Path(data_dir)
        self._ready = False

    def set_ready(self) -> None:
        """Mark the service as ready."""
        self._ready = True
        # Ensure the data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def ready(self) -> bool:
        """Check if the service is ready."""
        return self._ready

    @abstractmethod
    def build_full_path(self, flow_id: str, file_name: str) -> str:
        """Build the full path for a file."""

    @abstractmethod
    async def save_file(self, flow_id: str, file_name: str, data: bytes) -> None:
        """Save a file."""

    @abstractmethod
    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        """Retrieve a file."""

    @abstractmethod
    async def list_files(self, flow_id: str) -> list[str]:
        """List files in a flow."""

    @abstractmethod
    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file."""

    @abstractmethod
    async def get_file_size(self, flow_id: str, file_name: str) -> int:
        """Get the size of a file."""

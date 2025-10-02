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
        # TODO: FRAZ - prob need to move this to the specific storage service
        if data_dir is None:
            data_dir = Path.home() / ".lfx" / "data"
        self.data_dir = Path(data_dir)
        self._ready = False

    def set_ready(self) -> None:
        """Mark the service as ready."""
        self._ready = True
        # Ensure the data directory exists
        # TODO: FRAZ - prob need to move this to the specific storage service
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

    @abstractmethod
    def is_remote_path(self, path: str) -> bool:
        """Check if path is a remote storage path (e.g., S3 URI).

        Args:
            path: The path to check

        Returns:
            bool: True if path is a remote storage path, False otherwise
        """

    @abstractmethod
    def parse_path(self, path: str) -> tuple[str, str] | None:
        """Parse path into (flow_id, file_name) components.

        Args:
            path: The path to parse (can be local path or remote URI)

        Returns:
            tuple[str, str] | None: (flow_id, file_name) if valid path, None otherwise
        """

    @abstractmethod
    async def path_exists(self, flow_id: str, file_name: str) -> bool:
        """Check if file exists in storage.

        Args:
            flow_id: The flow ID where the file should be located
            file_name: The name of the file to check

        Returns:
            bool: True if file exists, False otherwise
        """

    @abstractmethod
    async def read_file(self, path: str) -> bytes:
        """Read file from any path format (unified interface).

        Args:
            path: The path to read from (can be local path or remote URI)

        Returns:
            bytes: The file content

        Raises:
            FileNotFoundError: If the file does not exist
        """

    @abstractmethod
    async def write_file(self, path: str, data: bytes, *, flow_id: str | None = None) -> str:
        """Write file and return final storage path.

        Args:
            path: The desired path or file name
            data: The file content to write
            flow_id: Optional flow ID for organizing files

        Returns:
            str: The final storage path where file was written

        Raises:
            ValueError: If path is invalid
        """

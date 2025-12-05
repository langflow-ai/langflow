"""Storage service for langflow - redirects to lfx implementation."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

import anyio

from langflow.services.base import Service

if TYPE_CHECKING:
    from collections.abc import Callable

    from langflow.services.session.service import SessionService
    from langflow.services.settings.service import SettingsService

# Constants for path parsing
EXPECTED_PATH_PARTS = 2  # Path format: "flow_id/filename"


class StorageService(Service):
    """Storage service for langflow."""

    name = "storage_service"

    @staticmethod
    def parse_storage_path(path: str) -> tuple[str, str] | None:
        """Parse a storage service path into flow_id and filename.

        Storage service paths follow the format: flow_id/filename

        Args:
            path: The storage service path in format "flow_id/filename"

        Returns:
            tuple[str, str] | None: (flow_id, filename) or None if invalid format
        """
        if not path or "/" not in path:
            return None

        parts = path.split("/", 1)
        if len(parts) != EXPECTED_PATH_PARTS or not parts[0] or not parts[1]:
            return None

        return parts[0], parts[1]

    def __init__(self, session_service: SessionService, settings_service: SettingsService):
        self.settings_service = settings_service
        self.session_service = session_service
        self.data_dir: anyio.Path = anyio.Path(settings_service.settings.config_dir)
        self.set_ready()

    def build_full_path(self, flow_id: str, file_name: str) -> str:
        raise NotImplementedError

    def set_ready(self) -> None:
        self.ready = True

    @abstractmethod
    async def save_file(self, flow_id: str, file_name: str, data: bytes, *, append: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    async def list_files(self, flow_id: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def get_file_size(self, flow_id: str, file_name: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def delete_file(self, flow_id: str, file_name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def read_file_bytes(self, file_path: str, resolve_path: Callable[[str], str] | None = None) -> bytes:
        """Read file bytes from storage.

        Args:
            file_path: Path to the file (format depends on storage type)
            resolve_path: Optional function to resolve relative paths to absolute paths
                         (typically Component.resolve_path). Only used for local storage.

        Returns:
            bytes: The file content

        Raises:
            FileNotFoundError: If the file doesn't exist
        """

    @abstractmethod
    async def read_file_bytes_from_path(self, file_path: str, resolve_path=None) -> bytes:
        """Read file bytes from storage using a file path.

        This is a convenience method for reading files when you have a path string.
        Each implementation handles path format appropriately:
        - S3: file_path should be in format "flow_id/filename"
        - Local: file_path can be absolute or relative (resolved via resolve_path)

        Args:
            file_path: Path to the file (format depends on storage type)
            resolve_path: Optional function to resolve relative paths to absolute paths
                         (typically Component.resolve_path). Only used for local storage.

        Returns:
            bytes: The file content

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file_path format is invalid
        """
        raise NotImplementedError

    @abstractmethod
    async def get_file_size_from_path(self, file_path: str, resolve_path=None) -> int:
        """Get the size of a file using a file path.

        This is a convenience method for getting file size when you have a path string.
        Each implementation handles path format appropriately:
        - S3: file_path should be in format "flow_id/filename"
        - Local: file_path can be absolute or relative (resolved via resolve_path)

        Args:
            file_path: Path to the file (format depends on storage type)
            resolve_path: Optional function to resolve relative paths to absolute paths
                         (typically Component.resolve_path). Only used for local storage.

        Returns:
            int: Size of the file in bytes

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file_path format is invalid
        """
        raise NotImplementedError
        raise NotImplementedError

    @abstractmethod
    async def read_file_text(
        self,
        file_path: str,
        encoding: str = "utf-8",
        resolve_path: Callable[[str], str] | None = None,
        newline: str | None = None,
    ) -> str:
        """Read file text from storage.

        Args:
            file_path: Path to the file (format depends on storage type)
            encoding: Text encoding to use
            resolve_path: Optional function to resolve relative paths to absolute paths
            newline: Newline mode (None for default, "" for universal newlines)

        Returns:
            str: The file content as text

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        raise NotImplementedError

    @abstractmethod
    async def file_exists(self, file_path: str) -> bool:
        """Check if a file exists in storage.

        Args:
            file_path: Path to the file (format depends on storage type)

        Returns:
            bool: True if the file exists
        """
        raise NotImplementedError

    async def teardown(self) -> None:
        raise NotImplementedError

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

import anyio

from langflow.services.base import Service

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

    from langflow.services.session.service import SessionService


class StorageService(Service):
    name = "storage_service"

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
    async def save_file(self, flow_id: str, file_name: str, data) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    async def list_files(self, flow_id: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def get_file_size(self, flow_id: str, file_name: str):
        raise NotImplementedError

    @abstractmethod
    async def delete_file(self, flow_id: str, file_name: str) -> None:
        raise NotImplementedError

    async def teardown(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_remote_path(self, path: str) -> bool:
        """Check if path is a remote storage path (e.g., S3 URI).

        Args:
            path: The path to check

        Returns:
            bool: True if path is a remote storage path, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def parse_path(self, path: str) -> tuple[str, str] | None:
        """Parse path into (flow_id, file_name) components.

        Args:
            path: The path to parse (can be local path or remote URI)

        Returns:
            tuple[str, str] | None: (flow_id, file_name) if valid path, None otherwise
        """
        raise NotImplementedError

    @abstractmethod
    async def path_exists(self, flow_id: str, file_name: str) -> bool:
        """Check if file exists in storage.

        Args:
            flow_id: The flow ID where the file should be located
            file_name: The name of the file to check

        Returns:
            bool: True if file exists, False otherwise
        """
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

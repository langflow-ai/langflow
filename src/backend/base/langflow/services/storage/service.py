"""Storage service for langflow - redirects to lfx implementation."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

import anyio

from langflow.services.base import Service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langflow.services.session.service import SessionService
    from langflow.services.settings.service import SettingsService


class StorageService(Service):
    """Storage service for langflow."""

    name = "storage_service"

    def __init__(self, session_service: SessionService, settings_service: SettingsService):
        self.settings_service = settings_service
        self.session_service = session_service
        self.data_dir: anyio.Path = anyio.Path(settings_service.settings.config_dir)
        self.set_ready()

    @abstractmethod
    def build_full_path(self, flow_id: str, file_name: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def parse_file_path(self, full_path: str) -> tuple[str, str]:
        """Parse a full storage path to extract flow_id and file_name.

        Args:
            full_path: Full path as returned by build_full_path

        Returns:
            tuple[str, str]: A tuple of (flow_id, file_name)

        Raises:
            ValueError: If the path format is invalid or doesn't match expected structure
        """
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
    def get_file_stream(self, flow_id: str, file_name: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Retrieve a file as a stream of chunks.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to retrieve
            chunk_size: Size of chunks to yield (default: 8192 bytes)

        Yields:
            bytes: Chunks of the file content

        Raises:
            FileNotFoundError: If the file does not exist
        """
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

    @abstractmethod
    async def teardown(self) -> None:
        raise NotImplementedError

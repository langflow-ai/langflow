"""Storage service for file and data management in Langflow.

This module provides the StorageService abstract base class that defines
the interface for file storage and data persistence operations, including:
- File upload, download, and management
- Data persistence and retrieval
- Storage backend abstraction (local, cloud, etc.)
- File path management and organization
- Integration with session and settings services
- Storage quota and access control
- Async file operations for performance

The StorageService enables flexible storage backends while providing
a consistent interface for file operations across the Langflow application.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

import anyio

from langflow.services.base import Service

if TYPE_CHECKING:
    from langflow.services.session.service import SessionService
    from langflow.services.settings.service import SettingsService


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
    async def delete_file(self, flow_id: str, file_name: str) -> None:
        raise NotImplementedError

    async def teardown(self) -> None:
        raise NotImplementedError

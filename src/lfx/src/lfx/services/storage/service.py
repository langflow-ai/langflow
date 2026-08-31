from __future__ import annotations

import uuid
from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import anyio

from lfx.services.base import Service

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.services.settings.service import SettingsService


@dataclass(frozen=True)
class StorageReadiness:
    """Result of a storage backend readiness probe (used by production preflight).

    Attributes:
        ok: True when the backend is usable (writable / reachable).
        backend: The configured backend identifier, e.g. "local" or "s3".
        detail: Human-readable one-line summary for display.
        reason: Machine-friendly failure reason when ``ok`` is False
            (e.g. "no-credentials", "bucket-missing", "access-denied",
            "unreachable", "unwritable"). Empty on success.
    """

    ok: bool
    backend: str
    detail: str
    reason: str = ""


class StorageService(Service):
    """Abstract base class for file storage services.

    This class defines the interface for file storage operations that can be
    implemented by different backends (local filesystem, S3, etc.).

    All file operations are namespaced by flow_id to isolate files between
    different flows or users.
    """

    name = "storage_service"

    def __init__(self, session_service, settings_service: SettingsService):
        """Initialize the storage service.

        Args:
            session_service: The session service instance
            settings_service: The settings service instance containing configuration
        """
        self.settings_service = settings_service
        self.session_service = session_service
        self.data_dir: anyio.Path = anyio.Path(settings_service.settings.config_dir)
        self.set_ready()

    @abstractmethod
    def build_full_path(self, flow_id: str, file_name: str) -> str:
        """Build the full path/key for a file.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file

        Returns:
            str: The full path or key for the file
        """
        raise NotImplementedError

    @abstractmethod
    def parse_file_path(self, full_path: str) -> tuple[str, str]:
        """Parse a full storage path to extract flow_id and file_name.

        This reverses the build_full_path operation.

        Args:
            full_path: Full path as returned by build_full_path

        Returns:
            tuple[str, str]: A tuple of (flow_id, file_name)

        Raises:
            ValueError: If the path format is invalid or doesn't match expected structure
        """
        raise NotImplementedError

    @abstractmethod
    def resolve_component_path(self, logical_path: str) -> str:
        """Convert a logical path to a format that components can use directly.

        Logical paths are in the format "{flow_id}/{filename}" as stored in the database.
        This method converts them to a format appropriate for the storage backend:
        - Local storage: Absolute filesystem path (/data_dir/flow_id/filename)
        - S3 storage: Logical path as-is (flow_id/filename)

        Components receive this resolved path and can use it without knowing the
        storage implementation details.

        Args:
            logical_path: Path in the format "flow_id/filename"

        Returns:
            str: A path that components can use directly
        """
        raise NotImplementedError

    def set_ready(self) -> None:
        """Mark the service as ready."""
        self._ready = True

    @abstractmethod
    async def save_file(self, flow_id: str, file_name: str, data: bytes, *, append: bool = False) -> None:
        """Save a file to storage.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to save
            data: The file content as bytes
            append: If True, append to existing file instead of overwriting.

        Raises:
            Exception: If the file cannot be saved
        """
        raise NotImplementedError

    @abstractmethod
    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        """Retrieve a file from storage.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to retrieve

        Returns:
            bytes: The file content

        Raises:
            FileNotFoundError: If the file does not exist
        """
        raise NotImplementedError

    async def get_file_stream(self, flow_id: str, file_name: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Retrieve a file from storage as a stream.

        Default implementation loads the entire file and yields it in chunks.
        Subclasses can override this for more efficient streaming.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to retrieve
            chunk_size: Size of chunks to yield (default: 8192 bytes)

        Yields:
            bytes: Chunks of the file content

        Raises:
            FileNotFoundError: If the file does not exist
        """
        # Default implementation - subclasses can override for true streaming
        content = await self.get_file(flow_id, file_name)
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]

    @abstractmethod
    async def list_files(self, flow_id: str) -> list[str]:
        """List all files in a flow's storage namespace.

        Args:
            flow_id: The flow/user identifier for namespacing

        Returns:
            list[str]: List of file names in the namespace

        Raises:
            FileNotFoundError: If the namespace directory does not exist
        """
        raise NotImplementedError

    @abstractmethod
    async def get_file_size(self, flow_id: str, file_name: str) -> int:
        """Get the size of a file in bytes.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file

        Returns:
            int: Size of the file in bytes

        Raises:
            FileNotFoundError: If the file does not exist
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file from storage.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to delete

        Note:
            Should not raise an error if the file doesn't exist
        """
        raise NotImplementedError

    async def check_readiness(self) -> StorageReadiness:
        """Probe whether this storage backend is usable, for production preflight.

        The default implementation targets a local filesystem ``data_dir``: it
        creates the directory if needed, writes and deletes a sentinel file to
        prove the backend is writable. Object-store backends (e.g. S3) override
        this with a credentials + reachability probe.

        Returns:
            StorageReadiness: ``ok=True`` when the backend is usable, otherwise a
            typed failure with a human-readable ``detail`` and a machine ``reason``.
        """
        backend = getattr(self.settings_service.settings, "storage_type", "local")
        try:
            await self.data_dir.mkdir(parents=True, exist_ok=True)
            sentinel = self.data_dir / f".langflow-preflight-{uuid.uuid4().hex}"
            await sentinel.write_bytes(b"ok")
            await sentinel.unlink()
        except OSError as exc:
            reason = getattr(exc, "strerror", None) or str(exc)
            return StorageReadiness(
                ok=False,
                backend=backend,
                detail=f"{self.data_dir} is not writable ({reason})",
                reason="unwritable",
            )
        return StorageReadiness(ok=True, backend=backend, detail=f"writable ({self.data_dir})")

    async def teardown(self) -> None:
        """Perform cleanup operations when the service is being shut down.

        Subclasses can override this to clean up any resources (connections, etc.).
        Default implementation is a no-op.
        """

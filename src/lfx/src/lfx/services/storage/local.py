"""Local file-based storage service for lfx package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiofile import async_open

from lfx.log.logger import logger
from lfx.services.base import Service
from lfx.services.storage.service import StorageService

if TYPE_CHECKING:
    from langflow.services.session.service import SessionService

    from lfx.services.settings.service import SettingsService

# Constants for path parsing
EXPECTED_PATH_PARTS = 2  # Path format: "flow_id/filename"


class LocalStorageService(StorageService, Service):
    """A service class for handling local file storage operations."""

    def __init__(
        self,
        session_service: SessionService,
        settings_service: SettingsService,
    ) -> None:
        """Initialize the local storage service.

        Args:
            session_service: Session service instance
            settings_service: Settings service instance containing configuration
        """
        # Initialize base class with services
        super().__init__(session_service, settings_service)
        # Base class already sets self.data_dir as anyio.Path from settings_service.settings.config_dir

    def resolve_component_path(self, logical_path: str) -> str:
        """Convert logical path to absolute filesystem path for local storage.

        Args:
            logical_path: Path in format "flow_id/filename"
        Returns:
            str: Absolute filesystem path
        """
        # Split the logical path into flow_id and filename
        parts = logical_path.split("/", 1)
        if len(parts) != EXPECTED_PATH_PARTS:
            # Handle edge case - return as-is if format is unexpected
            return logical_path

        flow_id, file_name = parts
        return self.build_full_path(flow_id, file_name)

    def build_full_path(self, flow_id: str, file_name: str) -> str:
        """Build the full path of a file in the local storage."""
        return str(self.data_dir / flow_id / file_name)

    def parse_file_path(self, full_path: str) -> tuple[str, str]:
        r"""Parse a full local storage path to extract flow_id and file_name.

        Args:
            full_path: Filesystem path, may or may not include data_dir
                e.g., "/data/user_123/image.png" or "user_123/image.png". On Windows the
                separators may be backslashes ("\\"). This method handles both.

        Returns:
            tuple[str, str]: A tuple of (flow_id, file_name)

        Examples:
            >>> parse_file_path("/data/user_123/image.png")  # with data_dir
            ("user_123", "image.png")
            >>> parse_file_path("user_123/image.png")  # without data_dir
            ("user_123", "image.png")
        """
        data_dir_str = str(self.data_dir)

        # Remove data_dir if present (but don't require it)
        path_without_prefix = full_path
        if full_path.startswith(data_dir_str):
            # Strip both POSIX and Windows separators
            path_without_prefix = full_path[len(data_dir_str) :].lstrip("/").lstrip("\\")

        # Normalize separators so downstream logic is platform-agnostic
        normalized_path = path_without_prefix.replace("\\", "/")

        # Split from the right to get the filename; everything before the last
        # "/" is the flow_id
        if "/" not in normalized_path:
            return "", normalized_path

        # Use rsplit to split from the right, limiting to 1 split
        flow_id, file_name = normalized_path.rsplit("/", 1)
        return flow_id, file_name

    async def save_file(self, flow_id: str, file_name: str, data: bytes, *, append: bool = False) -> None:
        """Save a file in the local storage.

        Args:
            flow_id: The identifier for the flow.
            file_name: The name of the file to be saved.
            data: The byte content of the file.
            append: If True, append to existing file; if False, overwrite.

        Raises:
            FileNotFoundError: If the specified flow does not exist.
            IsADirectoryError: If the file name is a directory.
            PermissionError: If there is no permission to write the file.
        """
        folder_path = self.data_dir / flow_id
        await folder_path.mkdir(parents=True, exist_ok=True)
        file_path = folder_path / file_name

        try:
            mode = "ab" if append else "wb"
            async with async_open(str(file_path), mode) as f:
                await f.write(data)
            action = "appended to" if append else "saved"
            await logger.ainfo(f"File {file_name} {action} successfully in flow {flow_id}.")
        except Exception:
            logger.exception(f"Error saving file {file_name} in flow {flow_id}")
            raise

    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        """Retrieve a file from the local storage.

        Args:
            flow_id: The identifier for the flow.
            file_name: The name of the file to be retrieved.

        Returns:
            The byte content of the file.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        file_path = self.data_dir / flow_id / file_name
        if not await file_path.exists():
            await logger.awarning(f"File {file_name} not found in flow {flow_id}.")
            msg = f"File {file_name} not found in flow {flow_id}"
            raise FileNotFoundError(msg)

        async with async_open(str(file_path), "rb") as f:
            content = await f.read()

        logger.debug(f"File {file_name} retrieved successfully from flow {flow_id}.")
        return content

    async def list_files(self, flow_id: str) -> list[str]:
        """List all files in a specific flow directory.

        Args:
            flow_id: The identifier for the flow.

        Returns:
            List of file names in the flow directory.
        """
        if not isinstance(flow_id, str):
            flow_id = str(flow_id)

        folder_path = self.data_dir / flow_id
        if not await folder_path.exists() or not await folder_path.is_dir():
            await logger.awarning(f"Flow {flow_id} directory does not exist.")
            return []

        try:
            files = [p.name async for p in folder_path.iterdir() if await p.is_file()]
        except Exception:  # noqa: BLE001
            logger.exception(f"Error listing files in flow {flow_id}")
            return []
        else:
            await logger.ainfo(f"Listed {len(files)} files in flow {flow_id}.")
            return files

    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file from the local storage.

        Args:
            flow_id: The identifier for the flow.
            file_name: The name of the file to be deleted.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        file_path = self.data_dir / flow_id / file_name
        if await file_path.exists():
            await file_path.unlink()
            await logger.ainfo(f"File {file_name} deleted successfully from flow {flow_id}.")
        else:
            await logger.awarning(f"Attempted to delete non-existent file {file_name} in flow {flow_id}.")

    async def get_file_size(self, flow_id: str, file_name: str) -> int:
        """Get the size of a file in bytes.

        Args:
            flow_id: The identifier for the flow.
            file_name: The name of the file.

        Returns:
            The size of the file in bytes.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        file_path = self.data_dir / flow_id / file_name
        if not await file_path.exists():
            await logger.awarning(f"File {file_name} not found in flow {flow_id}.")
            msg = f"File {file_name} not found in flow {flow_id}"
            raise FileNotFoundError(msg)

        try:
            file_size_stat = await file_path.stat()
        except Exception:
            logger.exception(f"Error getting size of file {file_name} in flow {flow_id}")
            raise
        else:
            return file_size_stat.st_size

    async def teardown(self) -> None:
        """Perform any cleanup operations when the service is being torn down."""
        # No specific teardown actions required for local

"""Local file-based storage service for lfx package."""

from pathlib import Path

from loguru import logger

from lfx.services.storage.service import StorageService


class LocalStorageService(StorageService):
    """A service class for handling local file storage operations."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        """Initialize the local storage service."""
        super().__init__(data_dir)
        self.set_ready()

    def build_full_path(self, flow_id: str, file_name: str) -> str:
        """Build the full path of a file in the local storage."""
        return str(self.data_dir / flow_id / file_name)

    async def save_file(self, flow_id: str, file_name: str, data: bytes) -> None:
        """Save a file in the local storage.

        Args:
            flow_id: The identifier for the flow.
            file_name: The name of the file to be saved.
            data: The byte content of the file.

        Raises:
            FileNotFoundError: If the specified flow does not exist.
            IsADirectoryError: If the file name is a directory.
            PermissionError: If there is no permission to write the file.
        """
        folder_path = self.data_dir / flow_id
        folder_path.mkdir(parents=True, exist_ok=True)
        file_path = folder_path / file_name

        try:
            with file_path.open("wb") as f:
                f.write(data)
        except Exception:
            logger.exception(f"Error saving file {file_name} in flow {flow_id}")
            raise
        else:
            logger.info(f"File {file_name} saved successfully in flow {flow_id}.")

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
        if not file_path.exists():
            logger.warning(f"File {file_name} not found in flow {flow_id}.")
            msg = f"File {file_name} not found in flow {flow_id}"
            raise FileNotFoundError(msg)

        try:
            with file_path.open("rb") as f:
                content = f.read()
        except Exception:
            logger.exception(f"Error reading file {file_name} in flow {flow_id}")
            raise
        else:
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
        if not folder_path.exists():
            logger.debug(f"Flow folder {flow_id} does not exist.")
            return []

        if not folder_path.is_dir():
            logger.warning(f"Flow path {flow_id} is not a directory.")
            return []

        try:
            files = [item.name for item in folder_path.iterdir() if item.is_file()]
        except Exception:  # noqa: BLE001
            logger.exception(f"Error listing files in flow {flow_id}")
            return []
        else:
            logger.debug(f"Listed {len(files)} files in flow {flow_id}.")
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
        if not file_path.exists():
            logger.warning(f"File {file_name} not found in flow {flow_id}.")
            msg = f"File {file_name} not found in flow {flow_id}"
            raise FileNotFoundError(msg)

        try:
            file_path.unlink()
            logger.info(f"File {file_name} deleted successfully from flow {flow_id}.")
        except Exception:
            logger.exception(f"Error deleting file {file_name} in flow {flow_id}")
            raise

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
        if not file_path.exists():
            logger.warning(f"File {file_name} not found in flow {flow_id}.")
            msg = f"File {file_name} not found in flow {flow_id}"
            raise FileNotFoundError(msg)

        try:
            size = file_path.stat().st_size
        except Exception:
            logger.exception(f"Error getting size of file {file_name} in flow {flow_id}")
            raise
        else:
            logger.debug(f"File {file_name} size: {size} bytes in flow {flow_id}.")
            return size

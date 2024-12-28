import anyio
from aiofile import async_open
from loguru import logger

from .service import StorageService


class LocalStorageService(StorageService):
    """A service class for handling local storage operations without aiofiles."""

    def __init__(self, session_service, settings_service) -> None:
        """Initialize the local storage service with session and settings services."""
        super().__init__(session_service, settings_service)
        self.data_dir = anyio.Path(settings_service.settings.config_dir)
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
        await folder_path.mkdir(parents=True, exist_ok=True)
        file_path = folder_path / file_name

        try:
            async with async_open(str(file_path), "wb") as f:
                await f.write(data)
            logger.info(f"File {file_name} saved successfully in flow {flow_id}.")
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
            logger.warning(f"File {file_name} not found in flow {flow_id}.")
            msg = f"File {file_name} not found in flow {flow_id}"
            raise FileNotFoundError(msg)

        async with async_open(str(file_path), "rb") as f:
            content = await f.read()

        logger.debug(f"File {file_name} retrieved successfully from flow {flow_id}.")
        return content

    async def list_files(self, flow_id: str):
        """List all files in a specified flow.

        Args:
            flow_id: The identifier for the flow.

        Returns:
            A list of file names.

        Raises:
            FileNotFoundError: If the flow directory does not exist.
        """
        if not isinstance(flow_id, str):
            flow_id = str(flow_id)
        folder_path = self.data_dir / flow_id
        if not await folder_path.exists() or not await folder_path.is_dir():
            logger.warning(f"Flow {flow_id} directory does not exist.")
            msg = f"Flow {flow_id} directory does not exist."
            raise FileNotFoundError(msg)

        files = [file.name async for file in folder_path.iterdir() if await file.is_file()]
        logger.info(f"Listed {len(files)} files in flow {flow_id}.")
        return files

    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file from the local storage.

        :param flow_id: The identifier for the flow.
        :param file_name: The name of the file to be deleted.
        """
        file_path = self.data_dir / flow_id / file_name
        if await file_path.exists():
            await file_path.unlink()
            logger.info(f"File {file_name} deleted successfully from flow {flow_id}.")
        else:
            logger.warning(f"Attempted to delete non-existent file {file_name} in flow {flow_id}.")

    async def teardown(self) -> None:
        """Perform any cleanup operations when the service is being torn down."""
        # No specific teardown actions required for local

import anyio
from aiofile import async_open
from lfx.log.logger import logger

from .service import StorageService


class LocalStorageService(StorageService):
    """A service class for handling local storage operations without aiofiles."""

    def __init__(self, session_service, settings_service) -> None:
        """Initialize the local storage service with session and settings services."""
        super().__init__(session_service, settings_service)
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
            await logger.ainfo(f"File {file_name} saved successfully in flow {flow_id}.")
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
            await logger.awarning(f"Flow {flow_id} directory does not exist.")
            msg = f"Flow {flow_id} directory does not exist."
            raise FileNotFoundError(msg)

        files = [
            file.name
            async for file in await anyio.to_thread.run_sync(folder_path.iterdir)
            if await anyio.Path(file).is_file()
        ]

        await logger.ainfo(f"Listed {len(files)} files in flow {flow_id}.")
        return files

    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file from the local storage.

        :param flow_id: The identifier for the flow.
        :param file_name: The name of the file to be deleted.
        """
        file_path = self.data_dir / flow_id / file_name
        if await file_path.exists():
            await file_path.unlink()
            await logger.ainfo(f"File {file_name} deleted successfully from flow {flow_id}.")
        else:
            await logger.awarning(f"Attempted to delete non-existent file {file_name} in flow {flow_id}.")

    async def teardown(self) -> None:
        """Perform any cleanup operations when the service is being torn down."""
        # No specific teardown actions required for local

    async def get_file_size(self, flow_id: str, file_name: str):
        """Get the size of a file in the local storage."""
        # Get the file size from the file path
        file_path = self.data_dir / flow_id / file_name
        if not await file_path.exists():
            await logger.awarning(f"File {file_name} not found in flow {flow_id}.")
            msg = f"File {file_name} not found in flow {flow_id}"
            raise FileNotFoundError(msg)

        file_size_stat = await file_path.stat()
        return file_size_stat.st_size

    def is_remote_path(self, path: str) -> bool:
        """Check if path is a remote storage path.

        For local storage, all paths are local, so this always returns False.

        Args:
            path: The path to check

        Returns:
            bool: Always False for local storage
        """
        return False

    def parse_path(self, path: str) -> tuple[str, str] | None:
        """Parse path into (flow_id, file_name) components.

        For local storage, we extract the flow_id from the path structure.
        Expected format: <data_dir>/<flow_id>/<file_name> or just <file_name>

        Args:
            path: The path to parse

        Returns:
            tuple[str, str] | None: (flow_id, file_name) if valid path, None otherwise
        """
        if not path or not isinstance(path, str):
            return None

        from pathlib import Path

        path_obj = Path(path)

        # Try to extract flow_id from path structure relative to data_dir
        try:
            # Convert anyio.Path to pathlib.Path for comparison
            data_dir_path = Path(str(self.data_dir))

            # If path is absolute and starts with data_dir
            if path_obj.is_absolute() and str(path_obj).startswith(str(data_dir_path)):
                relative = path_obj.relative_to(data_dir_path)
                parts = relative.parts
                if len(parts) >= 2:
                    # Format: flow_id/file_name
                    return (parts[0], "/".join(parts[1:]))
                if len(parts) == 1:
                    # Format: file_name (no flow_id in path)
                    return ("local", parts[0])
            else:
                # Just a filename or relative path
                return ("local", path_obj.name)
        except (ValueError, AttributeError):
            # If path is not relative to data_dir or has issues, use filename
            return ("local", path_obj.name)

        return None

    async def path_exists(self, flow_id: str, file_name: str) -> bool:
        """Check if file exists in local storage.

        Args:
            flow_id: The identifier for the flow
            file_name: The name of the file to check

        Returns:
            bool: True if file exists, False otherwise
        """
        file_path = self.data_dir / flow_id / file_name
        return await file_path.exists()

    async def read_file(self, path: str) -> bytes:
        """Read file from any path format (unified interface).

        Args:
            path: The path to read from (can be absolute or relative)

        Returns:
            bytes: The file content

        Raises:
            FileNotFoundError: If the file does not exist
        """
        # Parse the path to get flow_id and file_name
        parsed = self.parse_path(path)
        if not parsed:
            msg = f"Invalid path format: {path}"
            raise ValueError(msg)

        flow_id, file_name = parsed
        return await self.get_file(flow_id, file_name)

    async def write_file(self, path: str, data: bytes, *, flow_id: str | None = None) -> str:
        """Write file and return final storage path.

        Args:
            path: The desired path or file name
            data: The file content to write
            flow_id: Optional flow ID for organizing files (overrides path-based flow_id)

        Returns:
            str: The final storage path where file was written

        Raises:
            ValueError: If path is invalid
        """
        from pathlib import Path

        # If flow_id is explicitly provided, use it
        if flow_id:
            file_name = Path(path).name
        else:
            # Parse the path to extract flow_id and file_name
            parsed = self.parse_path(path)
            if not parsed:
                msg = f"Invalid path format: {path}"
                raise ValueError(msg)
            flow_id, file_name = parsed

        # Save the file
        await self.save_file(flow_id, file_name, data)

        # Return the full path
        return self.build_full_path(flow_id, file_name)

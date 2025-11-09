"""Local storage service for langflow - redirects to lfx implementation."""

from lfx.services.storage.local import LocalStorageService as LfxLocalStorageService

from .service import StorageService


class LocalStorageService(StorageService):
    """A service class for handling local storage operations.

    This is a thin wrapper around the lfx LocalStorageService implementation.
    """

    def __init__(self, session_service, settings_service) -> None:
        """Initialize the local storage service with session and settings services."""
        # Delegate to lfx implementation first
        self._lfx_service = LfxLocalStorageService(
            session_service=session_service,
            settings_service=settings_service,
        )
        # Initialize parent with services (this sets data_dir, but we'll override it)
        super().__init__(session_service, settings_service)
        # Override data_dir with lfx service's data_dir
        self.data_dir = self._lfx_service.data_dir
        self.set_ready()

    def build_full_path(self, flow_id: str, file_name: str) -> str:
        """Build the full path of a file in the local storage."""
        return self._lfx_service.build_full_path(flow_id, file_name)

    def resolve_component_path(self, logical_path: str) -> str:
        """Convert logical path to absolute filesystem path for local storage."""
        return self._lfx_service.resolve_component_path(logical_path)

    async def save_file(self, flow_id: str, file_name: str, data: bytes) -> None:
        """Save a file in the local storage."""
        return await self._lfx_service.save_file(flow_id, file_name, data)

    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        """Retrieve a file from the local storage."""
        return await self._lfx_service.get_file(flow_id, file_name)

    async def get_file_stream(self, flow_id: str, file_name: str, chunk_size: int = 8192):
        """Retrieve a file from storage as a stream."""
        return await self._lfx_service.get_file_stream(flow_id, file_name, chunk_size)

    async def list_files(self, flow_id: str) -> list[str]:
        """List all files in a specified flow."""
        return await self._lfx_service.list_files(flow_id)

    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file from the local storage."""
        return await self._lfx_service.delete_file(flow_id, file_name)

    async def get_file_size(self, flow_id: str, file_name: str) -> int:
        """Get the size of a file in the local storage."""
        return await self._lfx_service.get_file_size(flow_id, file_name)

    async def teardown(self) -> None:
        """Perform any cleanup operations when the service is being torn down."""
        return await self._lfx_service.teardown()

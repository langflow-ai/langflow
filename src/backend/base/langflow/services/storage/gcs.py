"""GCS-based storage service implementation using google-cloud-storage.

This service handles file storage operations with Google Cloud Storage, including
file upload, download, deletion, and listing operations. The official
google-cloud-storage client is synchronous, so blocking calls are offloaded to a
worker thread via asyncio.to_thread (the same pattern used by
langflow.services.variable.kubernetes for the synchronous Kubernetes client).
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from langflow.logging.logger import logger

from .service import StorageService

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from google.cloud.storage import Blob

    from langflow.services.session.service import SessionService
    from langflow.services.settings.service import SettingsService


class GCSStorageService(StorageService):
    """A service class for handling Google Cloud Storage operations using google-cloud-storage."""

    def __init__(self, session_service: SessionService, settings_service: SettingsService) -> None:
        """Initialize the GCS storage service with session and settings services.

        Args:
            session_service: The session service instance
            settings_service: The settings service instance

        Raises:
            ImportError: If google-cloud-storage is not installed
            ValueError: If required GCS configuration is missing
            RuntimeError: If the GCS client cannot be created (e.g. missing credentials)
        """
        super().__init__(session_service, settings_service)

        # Validate required GCS configuration
        self.bucket_name = settings_service.settings.object_storage_bucket_name
        if not self.bucket_name:
            msg = "GCS bucket name is required when using GCS storage"
            raise ValueError(msg)

        self.prefix = settings_service.settings.object_storage_prefix or ""
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"

        # GCS has no first-class object "tags" concept (tags/labels are bucket-level).
        # object_storage_tags is applied as custom metadata on each blob instead.
        self.tags = settings_service.settings.object_storage_tags or {}

        try:
            from google.cloud import storage
        except ImportError as exc:
            msg = (
                "google-cloud-storage is required for GCS storage. Install it with: uv pip install google-cloud-storage"
            )
            raise ImportError(msg) from exc

        try:
            # Credentials are picked up from GOOGLE_APPLICATION_CREDENTIALS or
            # Application Default Credentials (ADC); no explicit key material here.
            self._client = storage.Client()
        except Exception as exc:
            msg = (
                "Failed to create Google Cloud Storage client. Ensure GOOGLE_APPLICATION_CREDENTIALS "
                "is set or Application Default Credentials are configured."
            )
            raise RuntimeError(msg) from exc

        self._bucket = self._client.bucket(self.bucket_name)

        self.set_ready()
        logger.info(f"GCS storage initialized: bucket={self.bucket_name}, prefix={self.prefix}")

    def _validate_identifiers(self, flow_id: str, file_name: str | None = None) -> None:
        """Reject flow_id / file_name values that could escape the flow namespace.

        Mirrors the guard in the S3 backend (defense in depth for GHSA-rcjh-r59h-gq37):
        validation is synchronous and runs before any GCS call so a malformed input
        cannot be turned into a read of an arbitrary object key.
        """
        if (
            not isinstance(flow_id, str)
            or not flow_id
            or "/" in flow_id
            or "\\" in flow_id
            or ".." in flow_id
            or "\x00" in flow_id
        ):
            logger.error("Invalid flow_id contains path separators or traversal sequences")
            msg = "Invalid flow_id: contains path separators"
            raise ValueError(msg)

        if file_name is not None and (
            not isinstance(file_name, str)
            or not file_name
            or "/" in file_name
            or "\\" in file_name
            or ".." in file_name
            or "\x00" in file_name
        ):
            logger.error("Invalid file_name contains path separators or traversal sequences")
            msg = "Invalid file name: contains path separators"
            raise ValueError(msg)

    def build_full_path(self, flow_id: str, file_name: str) -> str:
        """Build the full GCS object name (key) for a file.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file

        Returns:
            str: The full object name (e.g., 'files/flow_123/myfile.txt')
        """
        # note: prefix already contains the / at the end
        return f"{self.prefix}{flow_id}/{file_name}"

    def parse_file_path(self, full_path: str) -> tuple[str, str]:
        """Parse a full GCS object name to extract flow_id and file_name.

        Args:
            full_path: GCS object name, may or may not include prefix
                e.g., "files/user_123/image.png" or "user_123/image.png"

        Returns:
            tuple[str, str]: A tuple of (flow_id, file_name)

        Examples:
            >>> parse_file_path("files/user_123/image.png")  # with prefix
            ("user_123", "image.png")
            >>> parse_file_path("user_123/image.png")  # without prefix
            ("user_123", "image.png")
        """
        # Remove prefix if present (but don't require it)
        path_without_prefix = full_path
        if self.prefix and full_path.startswith(self.prefix):
            path_without_prefix = full_path[len(self.prefix) :]

        # Split from the right to get the filename
        # Everything before the last "/" is the flow_id
        if "/" not in path_without_prefix:
            return "", path_without_prefix

        # Use rsplit to split from the right, limiting to 1 split
        flow_id, file_name = path_without_prefix.rsplit("/", 1)
        return flow_id, file_name

    def resolve_component_path(self, logical_path: str) -> str:
        """Return logical path as-is for GCS storage.

        For GCS, components work with logical paths (flow_id/filename) and the
        storage service adds the prefix internally when performing operations.

        Args:
            logical_path: Path in format "flow_id/filename"

        Returns:
            str: The same logical path (components use this with storage service)
        """
        return logical_path

    def _get_blob(self, key: str) -> Blob:
        return self._bucket.blob(key)

    def _upload_blob(self, key: str, data: bytes) -> None:
        blob = self._get_blob(key)
        if self.tags:
            blob.metadata = self.tags
        blob.upload_from_string(data)

    def _download_blob(self, key: str) -> bytes:
        return self._get_blob(key).download_as_bytes()

    def _get_existing_blob(self, key: str) -> Blob | None:
        """Return the populated Blob if it exists, else None (single HEAD-like call)."""
        return self._bucket.get_blob(key)

    def _delete_blob(self, key: str) -> None:
        self._get_blob(key).delete()

    def _list_blob_names(self, prefix: str) -> list[str]:
        return [blob.name for blob in self._client.list_blobs(self.bucket_name, prefix=prefix)]

    async def save_file(self, flow_id: str, file_name: str, data: bytes, *, append: bool = False) -> None:
        """Save a file to GCS.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be saved
            data: The byte content of the file
            append: If True, append to existing file (not supported in GCS, will raise error)

        Raises:
            Exception: If the file cannot be saved to GCS
            NotImplementedError: If append=True (not supported in GCS)
        """
        if append:
            msg = "Append mode is not supported for GCS storage"
            raise NotImplementedError(msg)

        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            from google.api_core.exceptions import Forbidden, NotFound

            await asyncio.to_thread(self._upload_blob, key, data)
            await logger.ainfo(f"File {file_name} saved successfully to GCS: gs://{self.bucket_name}/{key}")
        except NotFound as e:
            msg = f"GCS bucket '{self.bucket_name}' does not exist"
            logger.exception(f"Error saving file {file_name} to GCS in flow {flow_id}: {msg}")
            raise FileNotFoundError(msg) from e
        except Forbidden as e:
            msg = "Access denied to GCS bucket. Please check your GCS credentials and bucket permissions"
            logger.exception(f"Error saving file {file_name} to GCS in flow {flow_id}: {msg}")
            raise PermissionError(msg) from e
        except Exception as e:
            logger.exception(f"Error saving file {file_name} to GCS in flow {flow_id}")
            msg = f"Failed to save file to GCS: {e}"
            raise RuntimeError(msg) from e

    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        """Retrieve a file from GCS.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be retrieved

        Returns:
            bytes: The file content

        Raises:
            FileNotFoundError: If the file does not exist in GCS
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            from google.api_core.exceptions import NotFound

            content = await asyncio.to_thread(self._download_blob, key)
        except NotFound as e:
            await logger.awarning(f"File {file_name} not found in GCS flow {flow_id}")
            msg = f"File not found: {file_name}"
            raise FileNotFoundError(msg) from e
        else:
            logger.debug(f"File {file_name} retrieved successfully from GCS: gs://{self.bucket_name}/{key}")
            return content

    async def get_file_stream(self, flow_id: str, file_name: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Retrieve a file from GCS as a stream.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to retrieve
            chunk_size: Size of chunks to yield (default: 8192 bytes)

        Yields:
            bytes: Chunks of the file content

        Raises:
            FileNotFoundError: If the file does not exist in GCS
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        blob = await asyncio.to_thread(self._get_existing_blob, key)
        if blob is None:
            await logger.awarning(f"File {file_name} not found in GCS flow {flow_id}")
            msg = f"File not found: {file_name}"
            raise FileNotFoundError(msg)

        file_obj = await asyncio.to_thread(blob.open, "rb")
        try:
            while True:
                chunk = await asyncio.to_thread(file_obj.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(file_obj.close)

    async def list_files(self, flow_id: str) -> list[str]:
        """List all files in a specified GCS prefix (flow namespace).

        Args:
            flow_id: The flow/user identifier for namespacing

        Returns:
            list[str]: A list of file names (without the prefix)

        Raises:
            Exception: If there's an error listing files from GCS
        """
        self._validate_identifiers(flow_id)

        prefix = self.build_full_path(flow_id, "")

        try:
            blob_names = await asyncio.to_thread(self._list_blob_names, prefix)
        except Exception:
            logger.exception(f"Error listing files in GCS flow {flow_id}")
            raise
        else:
            # Remove the flow_id prefix to get just the filename, skip directory markers
            return [name[len(prefix) :] for name in blob_names if name[len(prefix) :]]

    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file from GCS.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be deleted

        Note:
            Matches the S3/local backends: deleting a non-existent file is a no-op.
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            from google.api_core.exceptions import NotFound

            await asyncio.to_thread(self._delete_blob, key)
        except NotFound:
            await logger.awarning(f"Attempted to delete non-existent file {file_name} in GCS flow {flow_id}")
        except Exception:
            logger.exception(f"Error deleting file {file_name} from GCS in flow {flow_id}")
            raise

    async def get_file_size(self, flow_id: str, file_name: str) -> int:
        """Get the size of a file in GCS.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file

        Returns:
            int: Size of the file in bytes

        Raises:
            FileNotFoundError: If the file does not exist in GCS
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            blob = await asyncio.to_thread(self._get_existing_blob, key)
        except Exception:
            logger.exception(f"Error getting file size for {file_name} in GCS flow {flow_id}")
            raise

        if blob is None or blob.size is None:
            await logger.awarning(f"File {file_name} not found in GCS flow {flow_id}")
            msg = f"File not found: {file_name}"
            raise FileNotFoundError(msg)

        return blob.size

    async def teardown(self) -> None:
        """Close the GCS client's HTTP session, if the installed SDK version exposes one."""
        close = getattr(self._client, "close", None)
        if callable(close):
            with contextlib.suppress(Exception):
                await asyncio.to_thread(close)
        logger.info("GCS storage service teardown complete")

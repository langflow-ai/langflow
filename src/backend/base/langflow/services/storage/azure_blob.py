"""Azure Blob Storage service implementation using azure-storage-blob.

This service handles file storage operations with Azure Blob Storage, including
file upload, download, deletion, and listing operations. It works against both
standard Blob Storage accounts and ADLS Gen2 (hierarchical namespace) accounts,
since ADLS Gen2 remains compatible with the flat Blob API used here.

Uses the official azure-storage-blob asyncio client (azure.storage.blob.aio), so
unlike the GCS backend no thread-offloading is required.
"""

from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING

from langflow.logging.logger import logger

from .service import StorageService

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langflow.services.session.service import SessionService
    from langflow.services.settings.service import SettingsService


class AzureBlobStorageService(StorageService):
    """A service class for handling Azure Blob Storage operations using azure-storage-blob."""

    def __init__(self, session_service: SessionService, settings_service: SettingsService) -> None:
        """Initialize the Azure Blob storage service with session and settings services.

        Args:
            session_service: The session service instance
            settings_service: The settings service instance

        Raises:
            ImportError: If azure-storage-blob (or azure-identity, when needed) is not installed
            ValueError: If required Azure configuration is missing
            RuntimeError: If the Azure Blob client cannot be created
        """
        super().__init__(session_service, settings_service)

        # object_storage_bucket_name doubles as the Azure Blob "container" name.
        self.container_name = settings_service.settings.object_storage_bucket_name
        if not self.container_name:
            msg = "Azure Blob container name is required when using Azure storage"
            raise ValueError(msg)

        self.prefix = settings_service.settings.object_storage_prefix or ""
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"

        # Applied as Blob Index Tags at upload time (Azure's equivalent of S3 object tags).
        self.tags = settings_service.settings.object_storage_tags or {}

        try:
            from azure.storage.blob.aio import BlobServiceClient
        except ImportError as exc:
            msg = (
                "azure-storage-blob is required for Azure Blob storage. "
                "Install it with: uv pip install azure-storage-blob"
            )
            raise ImportError(msg) from exc

        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
        account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")

        self._credential = None
        try:
            if connection_string:
                self._service_client = BlobServiceClient.from_connection_string(connection_string)
            elif account_url or account_name:
                resolved_account_url = account_url or f"https://{account_name}.blob.core.windows.net"
                try:
                    from azure.identity.aio import DefaultAzureCredential
                except ImportError as exc:
                    msg = (
                        "azure-identity is required for Azure Blob storage when not using "
                        "AZURE_STORAGE_CONNECTION_STRING. Install it with: uv pip install azure-identity"
                    )
                    raise ImportError(msg) from exc
                # Covers managed identity, AKS workload identity, service principal env
                # vars, and `az login` credentials without any Langflow-specific config.
                self._credential = DefaultAzureCredential()
                self._service_client = BlobServiceClient(account_url=resolved_account_url, credential=self._credential)
            else:
                msg = (
                    "Azure Blob storage requires AZURE_STORAGE_CONNECTION_STRING, or "
                    "AZURE_STORAGE_ACCOUNT_URL / AZURE_STORAGE_ACCOUNT_NAME with credentials "
                    "resolvable via DefaultAzureCredential (managed identity, workload identity, "
                    "service principal, or az login)"
                )
                raise ValueError(msg)
        except (ImportError, ValueError):
            raise
        except Exception as exc:
            msg = "Failed to create Azure Blob Storage client"
            raise RuntimeError(msg) from exc

        self._container_client = self._service_client.get_container_client(self.container_name)

        self.set_ready()
        logger.info(f"Azure Blob storage initialized: container={self.container_name}, prefix={self.prefix}")

    def _validate_identifiers(self, flow_id: str, file_name: str | None = None) -> None:
        """Reject flow_id / file_name values that could escape the flow namespace.

        Mirrors the guard in the S3/GCS backends (defense in depth for GHSA-rcjh-r59h-gq37):
        validation is synchronous and runs before any Azure call so a malformed input
        cannot be turned into a read of an arbitrary blob name.
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
        """Build the full Azure blob name for a file.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file

        Returns:
            str: The full blob name (e.g., 'files/flow_123/myfile.txt')
        """
        # note: prefix already contains the / at the end
        return f"{self.prefix}{flow_id}/{file_name}"

    def parse_file_path(self, full_path: str) -> tuple[str, str]:
        """Parse a full Azure blob name to extract flow_id and file_name.

        Args:
            full_path: Blob name, may or may not include prefix
                e.g., "files/user_123/image.png" or "user_123/image.png"

        Returns:
            tuple[str, str]: A tuple of (flow_id, file_name)

        Examples:
            >>> parse_file_path("files/user_123/image.png")  # with prefix
            ("user_123", "image.png")
            >>> parse_file_path("user_123/image.png")  # without prefix
            ("user_123", "image.png")
        """
        path_without_prefix = full_path
        if self.prefix and full_path.startswith(self.prefix):
            path_without_prefix = full_path[len(self.prefix) :]

        if "/" not in path_without_prefix:
            return "", path_without_prefix

        flow_id, file_name = path_without_prefix.rsplit("/", 1)
        return flow_id, file_name

    def resolve_component_path(self, logical_path: str) -> str:
        """Return logical path as-is for Azure Blob storage.

        For Azure Blob storage, components work with logical paths (flow_id/filename)
        and the storage service adds the prefix internally when performing operations.

        Args:
            logical_path: Path in format "flow_id/filename"

        Returns:
            str: The same logical path (components use this with storage service)
        """
        return logical_path

    def _get_blob_client(self, key: str):
        return self._container_client.get_blob_client(key)

    async def save_file(self, flow_id: str, file_name: str, data: bytes, *, append: bool = False) -> None:
        """Save a file to Azure Blob storage.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be saved
            data: The byte content of the file
            append: If True, append to existing file (not supported here, will raise error)

        Raises:
            Exception: If the file cannot be saved to Azure Blob storage
            NotImplementedError: If append=True (not supported)
        """
        if append:
            msg = "Append mode is not supported for Azure Blob storage"
            raise NotImplementedError(msg)

        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            from azure.core.exceptions import (
                ClientAuthenticationError,
                HttpResponseError,
                ResourceNotFoundError,
            )

            blob_client = self._get_blob_client(key)
            await blob_client.upload_blob(data, overwrite=True, tags=self.tags or None)
            await logger.ainfo(
                f"File {file_name} saved successfully to Azure Blob storage: {self.container_name}/{key}"
            )
        except ResourceNotFoundError as e:
            msg = f"Azure Blob container '{self.container_name}' does not exist"
            logger.exception(f"Error saving file {file_name} to Azure Blob storage in flow {flow_id}: {msg}")
            raise FileNotFoundError(msg) from e
        except ClientAuthenticationError as e:
            msg = "Authentication to Azure Blob storage failed. Please check your credentials"
            logger.exception(f"Error saving file {file_name} to Azure Blob storage in flow {flow_id}: {msg}")
            raise PermissionError(msg) from e
        except Exception as e:
            if isinstance(e, HttpResponseError) and e.status_code == 403:
                msg = "Access denied to Azure Blob container. Please check your role assignment and permissions"
                logger.exception(f"Error saving file {file_name} to Azure Blob storage in flow {flow_id}: {msg}")
                raise PermissionError(msg) from e
            logger.exception(f"Error saving file {file_name} to Azure Blob storage in flow {flow_id}")
            msg = f"Failed to save file to Azure Blob storage: {e}"
            raise RuntimeError(msg) from e

    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        """Retrieve a file from Azure Blob storage.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be retrieved

        Returns:
            bytes: The file content

        Raises:
            FileNotFoundError: If the file does not exist
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            from azure.core.exceptions import ResourceNotFoundError

            blob_client = self._get_blob_client(key)
            downloader = await blob_client.download_blob()
            content = await downloader.readall()
        except ResourceNotFoundError as e:
            await logger.awarning(f"File {file_name} not found in Azure Blob flow {flow_id}")
            msg = f"File not found: {file_name}"
            raise FileNotFoundError(msg) from e
        else:
            logger.debug(
                f"File {file_name} retrieved successfully from Azure Blob storage: {self.container_name}/{key}"
            )
            return content

    async def get_file_stream(self, flow_id: str, file_name: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Retrieve a file from Azure Blob storage as a stream.

        Downloads via a single request pinned to the blob's ETag (IfNotModified) and
        yields the SDK's own chunk boundaries via downloader.chunks(), so a blob that
        gets overwritten mid-stream raises instead of silently splicing together bytes
        from two different versions of the blob. chunk_size is accepted for interface
        parity with the other backends, but the actual chunk boundaries are determined
        by the Azure SDK's internal transfer settings, not this value.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to retrieve
            chunk_size: Unused; retained for interface parity with the other backends

        Yields:
            bytes: Chunks of the file content

        Raises:
            FileNotFoundError: If the file does not exist
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceNotFoundError

        blob_client = self._get_blob_client(key)
        try:
            properties = await blob_client.get_blob_properties()
            downloader = await blob_client.download_blob(
                etag=properties.etag, match_condition=MatchConditions.IfNotModified
            )
        except ResourceNotFoundError as e:
            await logger.awarning(f"File {file_name} not found in Azure Blob flow {flow_id}")
            msg = f"File not found: {file_name}"
            raise FileNotFoundError(msg) from e

        async for chunk in downloader.chunks():
            yield chunk

    async def list_files(self, flow_id: str) -> list[str]:
        """List all files in a specified Azure Blob prefix (flow namespace).

        Args:
            flow_id: The flow/user identifier for namespacing

        Returns:
            list[str]: A list of file names (without the prefix)

        Raises:
            Exception: If there's an error listing files from Azure Blob storage
        """
        self._validate_identifiers(flow_id)

        prefix = self.build_full_path(flow_id, "")

        try:
            blob_names = [blob.name async for blob in self._container_client.list_blobs(name_starts_with=prefix)]
        except Exception:
            logger.exception(f"Error listing files in Azure Blob flow {flow_id}")
            raise
        else:
            return [name[len(prefix) :] for name in blob_names if name[len(prefix) :]]

    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file from Azure Blob storage.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be deleted

        Note:
            Matches the S3/GCS/local backends: deleting a non-existent file is a no-op.
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            from azure.core.exceptions import ResourceNotFoundError

            blob_client = self._get_blob_client(key)
            await blob_client.delete_blob()
        except ResourceNotFoundError:
            await logger.awarning(f"Attempted to delete non-existent file {file_name} in Azure Blob flow {flow_id}")
        except Exception:
            logger.exception(f"Error deleting file {file_name} from Azure Blob storage in flow {flow_id}")
            raise

    async def get_file_size(self, flow_id: str, file_name: str) -> int:
        """Get the size of a file in Azure Blob storage.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file

        Returns:
            int: Size of the file in bytes

        Raises:
            FileNotFoundError: If the file does not exist
        """
        self._validate_identifiers(flow_id, file_name)
        key = self.build_full_path(flow_id, file_name)

        try:
            from azure.core.exceptions import ResourceNotFoundError

            blob_client = self._get_blob_client(key)
            properties = await blob_client.get_blob_properties()
        except ResourceNotFoundError as e:
            await logger.awarning(f"File {file_name} not found in Azure Blob flow {flow_id}")
            msg = f"File not found: {file_name}"
            raise FileNotFoundError(msg) from e
        except Exception:
            logger.exception(f"Error getting file size for {file_name} in Azure Blob flow {flow_id}")
            raise
        else:
            return properties.size

    async def teardown(self) -> None:
        """Close the underlying Azure SDK clients and credential.

        Unlike S3 (per-call context managers) or GCS (a plain sync client), the
        azure-storage-blob asyncio clients hold a persistent aiohttp session that
        must be closed explicitly to avoid "unclosed session" warnings.
        """
        with contextlib.suppress(Exception):
            await self._container_client.close()
        with contextlib.suppress(Exception):
            await self._service_client.close()
        if self._credential is not None:
            with contextlib.suppress(Exception):
                await self._credential.close()
        logger.info("Azure Blob storage service teardown complete")

"""S3-based storage service implementation using async boto3.

This service handles file storage operations with AWS S3, including
file upload, download, deletion, and listing operations.
"""

from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING, Any

from langflow.logging.logger import logger

from .service import StorageService

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langflow.services.session.service import SessionService
    from langflow.services.settings.service import SettingsService


class S3StorageService(StorageService):
    """A service class for handling S3 storage operations using aioboto3."""

    def __init__(self, session_service: SessionService, settings_service: SettingsService) -> None:
        """Initialize the S3 storage service with session and settings services.

        Args:
            session_service: The session service instance
            settings_service: The settings service instance

        Raises:
            ImportError: If aioboto3 is not installed
            ValueError: If required S3 configuration is missing
        """
        super().__init__(session_service, settings_service)

        # Validate required S3 configuration
        self.bucket_name = settings_service.settings.object_storage_bucket_name
        if not self.bucket_name:
            msg = "S3 bucket name is required when using S3 storage"
            raise ValueError(msg)

        self.prefix = settings_service.settings.object_storage_prefix or ""
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"

        self.tags = settings_service.settings.object_storage_tags or {}

        try:
            import aioboto3
        except ImportError as exc:
            msg = "aioboto3 is required for S3 storage. Install it with: uv pip install aioboto3"
            raise ImportError(msg) from exc

        # Create session - AWS credentials are picked up from environment variables
        self.session = aioboto3.Session()
        self._client = None

        self.set_ready()
        logger.info(
            f"S3 storage initialized: bucket={self.bucket_name}, prefix={self.prefix}, "
            f"region={os.getenv('AWS_DEFAULT_REGION', 'default')}"
        )

    def build_full_path(self, flow_id: str, file_name: str) -> str:
        """Build the full S3 key for a file.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file

        Returns:
            str: The full S3 key (e.g., 'files/flow_123/myfile.txt')
        """
        # note: prefix already contains the / at the end
        return f"{self.prefix}{flow_id}/{file_name}"

    def parse_file_path(self, full_path: str) -> tuple[str, str]:
        """Parse a full S3 path to extract flow_id and file_name.

        Args:
            full_path: S3 path, may or may not include prefix
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
        """Return logical path as-is for S3 storage.

        For S3, components work with logical paths (flow_id/filename) and the
        storage service adds the prefix internally when performing operations.

        Args:
            logical_path: Path in format "flow_id/filename"

        Returns:
            str: The same logical path (components use this with storage service)
        """
        return logical_path

    def _get_client(self):
        """Get or create an S3 client using the async context manager."""
        return self.session.client("s3")

    async def save_file(self, flow_id: str, file_name: str, data: bytes, *, append: bool = False) -> None:
        """Save a file to S3.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be saved
            data: The byte content of the file
            append: If True, append to existing file (not supported in S3, will raise error)

        Raises:
            Exception: If the file cannot be saved to S3
            NotImplementedError: If append=True (not supported in S3)
        """
        if append:
            msg = "Append mode is not supported for S3 storage"
            raise NotImplementedError(msg)

        key = self.build_full_path(flow_id, file_name)

        try:
            async with self._get_client() as s3_client:
                put_params: dict[str, Any] = {
                    "Bucket": self.bucket_name,
                    "Key": key,
                    "Body": data,
                }

                if self.tags:
                    tag_string = "&".join([f"{k}={v}" for k, v in self.tags.items()])
                    put_params["Tagging"] = tag_string

                await s3_client.put_object(**put_params)

            await logger.ainfo(f"File {file_name} saved successfully to S3: s3://{self.bucket_name}/{key}")

        except Exception as e:
            error_msg = str(e)
            error_code = None

            if hasattr(e, "response") and isinstance(e.response, dict):
                error_info = e.response.get("Error", {})
                error_code = error_info.get("Code")
                error_msg = error_info.get("Message", str(e))

            logger.exception(f"Error saving file {file_name} to S3 in flow {flow_id}: {error_msg}")

            if error_code == "NoSuchBucket":
                msg = f"S3 bucket '{self.bucket_name}' does not exist"
                raise FileNotFoundError(msg) from e
            if error_code == "AccessDenied":
                msg = "Access denied to S3 bucket. Please check your AWS credentials and bucket permissions"
                raise PermissionError(msg) from e
            if error_code == "InvalidAccessKeyId":
                msg = "Invalid AWS credentials. Please check your AWS access key and secret key"
                raise PermissionError(msg) from e
            msg = f"Failed to save file to S3: {error_msg}"
            raise RuntimeError(msg) from e

    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        """Retrieve a file from S3.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be retrieved

        Returns:
            bytes: The file content

        Raises:
            FileNotFoundError: If the file does not exist in S3
        """
        key = self.build_full_path(flow_id, file_name)

        try:
            async with self._get_client() as s3_client:
                response = await s3_client.get_object(Bucket=self.bucket_name, Key=key)
                content = await response["Body"].read()

            logger.debug(f"File {file_name} retrieved successfully from S3: s3://{self.bucket_name}/{key}")
        except Exception as e:
            if hasattr(e, "response") and e.response.get("Error", {}).get("Code") == "NoSuchKey":
                await logger.awarning(f"File {file_name} not found in S3 flow {flow_id}")
                msg = f"File not found: {file_name}"
                raise FileNotFoundError(msg) from e

            logger.exception(f"Error retrieving file {file_name} from S3 in flow {flow_id}")
            raise
        else:
            return content

    async def get_file_stream(self, flow_id: str, file_name: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Retrieve a file from S3 as a stream.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to retrieve
            chunk_size: Size of chunks to yield (default: 8192 bytes)

        Yields:
            bytes: Chunks of the file content

        Raises:
            FileNotFoundError: If the file does not exist in S3
        """
        key = self.build_full_path(flow_id, file_name)

        try:
            async with self._get_client() as s3_client:
                response = await s3_client.get_object(Bucket=self.bucket_name, Key=key)
                body = response["Body"]

                try:
                    async for chunk in body.iter_chunks(chunk_size):
                        yield chunk
                finally:
                    if hasattr(body, "close"):
                        with contextlib.suppress(Exception):
                            await body.close()

            logger.debug(f"File {file_name} streamed successfully from S3: s3://{self.bucket_name}/{key}")

        except Exception as e:
            if hasattr(e, "response") and e.response.get("Error", {}).get("Code") == "NoSuchKey":
                await logger.awarning(f"File {file_name} not found in S3 flow {flow_id}")
                msg = f"File not found: {file_name}"
                raise FileNotFoundError(msg) from e

            logger.exception(f"Error streaming file {file_name} from S3 in flow {flow_id}")
            raise

    async def list_files(self, flow_id: str) -> list[str]:
        """List all files in a specified S3 prefix (flow namespace).

        Args:
            flow_id: The flow/user identifier for namespacing

        Returns:
            list[str]: A list of file names (without the prefix)

        Raises:
            Exception: If there's an error listing files from S3
        """
        if not isinstance(flow_id, str):
            flow_id = str(flow_id)

        prefix = self.build_full_path(flow_id, "")

        try:
            async with self._get_client() as s3_client:
                paginator = s3_client.get_paginator("list_objects_v2")
                files = []

                async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                    if "Contents" in page:
                        for obj in page["Contents"]:
                            # Extract just the filename (remove the prefix)
                            full_key = obj["Key"]
                            # Remove the flow_id prefix to get just the filename
                            file_name = full_key[len(prefix) :]
                            if file_name:  # Skip the directory marker if it exists
                                files.append(file_name)

            await logger.ainfo(f"Listed {len(files)} files in S3 flow {flow_id}")
        except Exception:
            logger.exception(f"Error listing files in S3 flow {flow_id}")
            raise
        else:
            return files

    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file from S3.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file to be deleted

        Note:
            S3 delete_object doesn't raise an error if the object doesn't exist
        """
        key = self.build_full_path(flow_id, file_name)

        try:
            async with self._get_client() as s3_client:
                await s3_client.delete_object(Bucket=self.bucket_name, Key=key)

            await logger.ainfo(f"File {file_name} deleted successfully from S3: s3://{self.bucket_name}/{key}")

        except Exception:
            logger.exception(f"Error deleting file {file_name} from S3 in flow {flow_id}")
            raise

    async def get_file_size(self, flow_id: str, file_name: str) -> int:
        """Get the size of a file in S3.

        Args:
            flow_id: The flow/user identifier for namespacing
            file_name: The name of the file

        Returns:
            int: Size of the file in bytes

        Raises:
            FileNotFoundError: If the file does not exist in S3
        """
        key = self.build_full_path(flow_id, file_name)

        try:
            async with self._get_client() as s3_client:
                response = await s3_client.head_object(Bucket=self.bucket_name, Key=key)
                file_size = response["ContentLength"]

            logger.debug(f"File {file_name} size: {file_size} bytes")
        except Exception as e:
            # Check if it's a 404 error
            if hasattr(e, "response") and e.response.get("Error", {}).get("Code") in ["NoSuchKey", "404"]:
                await logger.awarning(f"File {file_name} not found in S3 flow {flow_id}")
                msg = f"File not found: {file_name}"
                raise FileNotFoundError(msg) from e

            logger.exception(f"Error getting file size for {file_name} in S3 flow {flow_id}")
            raise
        else:
            return file_size

    async def teardown(self) -> None:
        """Perform any cleanup operations when the service is being torn down.

        For S3, we don't need to do anything as aioboto3 handles cleanup
        via context managers.
        """
        logger.info("S3 storage service teardown complete")

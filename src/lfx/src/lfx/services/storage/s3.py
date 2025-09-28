import re
from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from lfx.log.logger import logger

from .service import StorageService


MAX_KEY_LENGTH = 1024
MAX_TAG_KEY_LENGTH = 128
MAX_TAG_VALUE_LENGTH = 256
MAX_TAGS_PER_OBJECT = 10

class S3StorageService(StorageService):
    """A service class for handling operations with AWS S3 storage."""

    def __init__(self, settings_service) -> None:
        """Initialize the S3 storage service.

        Args:
            settings_service: Settings service for configuration
        """
        super().__init__()

        # Get object storage configuration from settings service
        self.bucket_name = getattr(settings_service.settings, "object_storage_bucket_name", None)
        self.object_prefix = getattr(settings_service.settings, "object_storage_prefix", None)
        self.tags = getattr(settings_service.settings, "object_storage_tags", None)

        if not self.bucket_name:
            msg = (
                "Object storage bucket name is required. Set LANGFLOW_OBJECT_STORAGE_BUCKET_NAME environment variable."
            )
            logger.error(msg)
            raise ValueError(msg)

        if not self.object_prefix:
            msg = "Object storage prefix cannot be empty. Set LANGFLOW_OBJECT_STORAGE_PREFIX environment variable."
            logger.error(msg)
            raise ValueError(msg)

        try:
            # Will use the default us-east-1 region if not specified in the ~/.aws/config file
            self.s3_client = boto3.client("s3")
            logger.debug("S3 client initialized for object storage")
        except Exception:
            logger.exception("Failed to initialize S3 client")
            raise

        self.set_ready()

    def _validate_path_component(self, component: str, component_name: str) -> str:
        """Validate and sanitize path components to prevent path traversal attacks.

        Args:
            component: The path component to validate (flow_id or file_name)
            component_name: Name for error messages

        Returns:
            Sanitized component

        Raises:
            ValueError: If component contains invalid characters or patterns
        """
        if not component or not isinstance(component, str):
            msg = f"{component_name} must be a non-empty string"
            raise ValueError(msg)

        # Check for path traversal patterns
        dangerous_patterns = [
            "..",  # Parent directory
            "/",  # Path separator
            "\\",  # Windows path separator
            "%2f",  # URL-encoded forward slash
            "%5c",  # URL-encoded backslash
            "%2e%2e",  # URL-encoded ..
        ]

        component_lower = component.lower()
        for pattern in dangerous_patterns:
            if pattern in component_lower:
                msg = f"{component_name} contains invalid pattern '{pattern}': {component}"
                raise ValueError(msg)

        # Remove any control characters and excessive whitespace
        sanitized = re.sub(r"[\x00-\x1f\x7f]", "", component).strip()

        # Ensure it's not empty after sanitization
        if not sanitized:
            logger.warning(
                f"'{component_name}' is empty after sanitization: {component}. Likely includes invalid characters or patterns"
            )
            msg = f"Component '{component_name}' contains invalid characters or patterns. Try removing these patterns: [.., /, \\, %2f, %5c, %2e%2e]"
            raise ValueError(msg)

        if len(sanitized) > MAX_KEY_LENGTH:
            msg = f"Component '{component_name}' length exceeds the maximum allowed length of {MAX_KEY_LENGTH} bytes: {len(sanitized)} bytes"
            raise ValueError(msg)

        return sanitized

    def _validate_tags(self, tags: dict) -> None:
        """Validate S3 tags according to AWS limits.

        Args:
            tags: Dictionary of tag key-value pairs

        Raises:
            ValueError: If tags violate AWS limits
        """
        if len(tags) > MAX_TAGS_PER_OBJECT:
            msg = f"Too many tags: {len(tags)}. AWS S3 allows maximum {MAX_TAGS_PER_OBJECT} tags per object"
            raise ValueError(msg)

        for key, value in tags.items():
            key_str = str(key)
            value_str = str(value)

            if len(key_str) > MAX_TAG_KEY_LENGTH:
                msg = f"Tag key too long: '{key_str[:50]}...' ({len(key_str)} chars). AWS S3 allows maximum {MAX_TAG_KEY_LENGTH} characters"
                raise ValueError(msg)

            if len(value_str) > MAX_TAG_VALUE_LENGTH:
                msg = f"Tag value too long for key '{key_str}': '{value_str[:50]}...' ({len(value_str)} chars). AWS S3 allows maximum {MAX_TAG_VALUE_LENGTH} characters"
                raise ValueError(msg)

    def _build_s3_key(self, flow_id: str, file_name: str) -> str:
        """Build and validate S3 key with security checks.

        Args:
            flow_id: The flow ID
            file_name: The file name

        Returns:
            Safe S3 key
        """
        # Validate and sanitize inputs
        safe_flow_id = self._validate_path_component(flow_id, "flow_id")
        safe_file_name = self._validate_path_component(file_name, "file_name")

        # Build the key
        return f"{self.object_prefix}/{safe_flow_id}/{safe_file_name}"

    def build_full_path(self, flow_id: str, file_name: str) -> str:
        """Build the full S3 path for a file.

        Args:
            flow_id: The flow ID
            file_name: The file name

        Returns:
            Full S3 path (s3://bucket/path/flow_id/file_name)
        """
        key = self._build_s3_key(flow_id, file_name)
        return f"s3://{self.bucket_name}/{key}"

    async def save_file(self, flow_id: str, file_name: str, data: bytes) -> None:
        """Save a file to the S3 bucket.

        Args:
            flow_id: The flow ID to save the file under.
            file_name: The name of the file to be saved.
            data: The byte content of the file.

        Raises:
            Exception: If an error occurs during file saving.
        """
        if not isinstance(data, bytes):
            msg = f"Expected bytes, got {type(data)}"
            raise TypeError(msg)

        if self.s3_client is None:
            msg = "S3 client not initialized"
            raise RuntimeError(msg)

        try:
            key = self._build_s3_key(flow_id, file_name)

            # Prepare put_object arguments
            put_args = {"Bucket": self.bucket_name, "Key": key, "Body": data}

            # Add tags if configured
            if self.tags:
                self._validate_tags(self.tags)
                tag_pairs = [f"{quote(str(k))}={quote(str(v))}" for k, v in self.tags.items()]
                put_args["Tagging"] = "&".join(tag_pairs)

            self.s3_client.put_object(**put_args)
            await logger.ainfo(f"File {file_name} saved successfully in flow {flow_id}.")
        except NoCredentialsError:
            await logger.aexception("Credentials not available for AWS S3.")
            raise
        except ClientError:
            await logger.aexception(f"Error saving file {file_name} in flow {flow_id}")
            raise

    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        """Retrieve a file from the S3 bucket.

        Args:
            flow_id: The flow ID where the file is stored.
            file_name: The name of the file to be retrieved.

        Returns:
            The byte content of the file.

        Raises:
            Exception: If an error occurs during file retrieval.
        """
        if self.s3_client is None:
            msg = "S3 client not initialized"
            raise RuntimeError(msg)

        try:
            key = self._build_s3_key(flow_id, file_name)
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            await logger.ainfo(f"File {file_name} retrieved successfully from flow {flow_id}.")
            return response["Body"].read()
        except ClientError:
            await logger.aexception(f"Error retrieving file {file_name} from flow {flow_id}")
            raise

    async def list_files(self, flow_id: str) -> list[str]:
        """List all files in a specified flow of the S3 bucket.

        Args:
            flow_id: The flow ID to list files from.

        Returns:
            A list of file names.

        Raises:
            Exception: If an error occurs during file listing.
        """
        if self.s3_client is None:
            msg = "S3 client not initialized"
            raise RuntimeError(msg)

        try:
            # Validate flow_id for list operation
            safe_flow_id = self._validate_path_component(flow_id, "flow_id")
            prefix = f"{self.object_prefix}/{safe_flow_id}/"
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
        except ClientError:
            await logger.aexception(f"Error listing files in flow {flow_id}")
            raise

        files = [item["Key"] for item in response.get("Contents", []) if "/" not in item["Key"][len(prefix) :]]
        await logger.ainfo(f"{len(files)} files listed in flow {flow_id}.")
        return files

    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file from the S3 bucket.

        Args:
            flow_id: The flow ID where the file is stored.
            file_name: The name of the file to be deleted.

        Raises:
            Exception: If an error occurs during file deletion.
        """
        if self.s3_client is None:
            msg = "S3 client not initialized"
            raise RuntimeError(msg)

        try:
            key = self._build_s3_key(flow_id, file_name)
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            await logger.ainfo(f"File {file_name} deleted successfully from flow {flow_id}.")
        except ClientError:
            await logger.aexception(f"Error deleting file {file_name} from flow {flow_id}")
            raise

    async def get_file_size(self, flow_id: str, file_name: str) -> int:
        """Get the size of a file in the S3 bucket.

        Args:
            flow_id: The flow ID where the file is stored.
            file_name: The name of the file to get the size for.

        Returns:
            The size of the file in bytes.

        Raises:
            Exception: If an error occurs during file size retrieval.
        """
        if self.s3_client is None:
            msg = "S3 client not initialized"
            raise RuntimeError(msg)

        try:
            key = self._build_s3_key(flow_id, file_name)
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            file_size = response["ContentLength"]
            await logger.ainfo(f"File {file_name} size retrieved successfully from flow {flow_id}: {file_size} bytes.")
        except ClientError:
            await logger.aexception(f"Error getting file size for {file_name} from flow {flow_id}")
            raise
        else:
            return file_size

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

    name = "storage_service"

    def __init__(self, settings_service, session_service=None) -> None:
        """Initialize the S3 storage service.

        Args:
            settings_service: Settings service for configuration
            session_service: Optional session service (for compatibility)
        """
        super().__init__()
        self.settings_service = settings_service
        self.session_service = session_service

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
        logger.debug(
            f"S3StorageService initialized - bucket: {self.bucket_name}, prefix: {self.object_prefix}, tags: {self.tags}"
        )

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
        except NoCredentialsError as e:
            await logger.aerror("Credentials not available for AWS S3: %s", e)
            raise RuntimeError("AWS S3 credentials not configured. Please check your AWS credentials.") from e
        except ClientError as e:
            await logger.aerror(f"Error saving file {file_name} in flow {flow_id}")
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            raise RuntimeError(f"S3 error ({error_code}): {error_message}") from e

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
        except ClientError as e:
            await logger.aexception(f"Error retrieving file {file_name} from flow {flow_id}")
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            raise RuntimeError(f"S3 error ({error_code}): {error_message}") from e

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

    async def teardown(self) -> None:
        """Perform any cleanup operations when the service is being torn down."""
        # No specific teardown actions required for S3 client

    def is_remote_path(self, path: str) -> bool:
        """Check if path is a remote storage path (S3 URI).

        Args:
            path: The path to check

        Returns:
            bool: True if path is an S3 URI (starts with s3://), False otherwise
        """
        return isinstance(path, str) and path.startswith("s3://")

    def parse_path(self, path: str) -> tuple[str, str] | None:
        """Parse S3 path into (flow_id, file_name) components.

        Expected format: s3://bucket/prefix/flow_id/file_name

        Args:
            path: The S3 URI to parse

        Returns:
            tuple[str, str] | None: (flow_id, file_name) if valid S3 URI, None otherwise
        """
        if not self.is_remote_path(path):
            return None

        # Remove s3:// prefix and split into parts
        path_parts = path[5:].split("/")

        # We need at least: bucket/prefix/flow_id/file_name (4 parts minimum)
        if len(path_parts) < 4:
            return None

        # Extract flow_id (second to last) and file_name (last)
        flow_id = path_parts[-2]
        file_name = path_parts[-1]

        return (flow_id, file_name)

    async def path_exists(self, flow_id: str, file_name: str) -> bool:
        """Check if file exists in S3 storage.

        Args:
            flow_id: The identifier for the flow
            file_name: The name of the file to check

        Returns:
            bool: True if file exists, False otherwise
        """
        if self.s3_client is None:
            msg = "S3 client not initialized"
            raise RuntimeError(msg)

        try:
            key = self._build_s3_key(flow_id, file_name)
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            # If error code is 404, file doesn't exist
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                return False
            # For other errors, re-raise
            await logger.aerror(f"Error checking if file {file_name} exists in flow {flow_id}: {e}")
            raise

    async def read_file(self, path: str) -> bytes:
        """Read file from S3 URI (unified interface).

        Args:
            path: The S3 URI to read from (e.g., s3://bucket/prefix/flow_id/file_name)

        Returns:
            bytes: The file content

        Raises:
            ValueError: If S3 URI is invalid
            FileNotFoundError: If the file does not exist
        """
        # Parse the S3 URI
        parsed = self.parse_path(path)
        if not parsed:
            msg = f"Invalid S3 URI format: {path}"
            raise ValueError(msg)

        flow_id, file_name = parsed
        return await self.get_file(flow_id, file_name)

    async def write_file(self, path: str, data: bytes, *, flow_id: str | None = None) -> str:
        """Write file to S3 and return final storage path.

        Args:
            path: The desired S3 URI or file name
            data: The file content to write
            flow_id: Optional flow ID for organizing files (overrides path-based flow_id)

        Returns:
            str: The final S3 URI where file was written

        Raises:
            ValueError: If path is invalid or flow_id cannot be determined
        """
        # If flow_id is explicitly provided, use it
        if flow_id:
            # Extract just the filename from path
            if self.is_remote_path(path):
                parsed = self.parse_path(path)
                file_name = parsed[1] if parsed else path.split("/")[-1]
            else:
                file_name = path.split("/")[-1]
        else:
            # Parse the path to extract flow_id and file_name
            if self.is_remote_path(path):
                parsed = self.parse_path(path)
                if not parsed:
                    msg = f"Invalid S3 URI format: {path}"
                    raise ValueError(msg)
                flow_id, file_name = parsed
            else:
                # If path is not an S3 URI, we need flow_id to be provided
                msg = f"flow_id must be provided when path is not an S3 URI: {path}"
                raise ValueError(msg)

        # Save the file
        await self.save_file(flow_id, file_name, data)

        # Return the full S3 URI
        return self.build_full_path(flow_id, file_name)

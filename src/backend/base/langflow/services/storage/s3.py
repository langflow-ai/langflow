import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from lfx.log.logger import logger
from lfx.services.settings.constants import DEFAULT_S3_BUCKET_NAME, DEFAULT_S3_REGION_NAME

from .service import StorageService


class S3StorageService(StorageService):
    """A service class for handling operations with AWS S3 storage."""

    def __init__(self, session_service, settings_service) -> None:
        """Initialize the S3 storage service with session and settings services."""
        super().__init__(session_service, settings_service)

        # Get S3 configuration from settings
        self.bucket = getattr(settings_service.settings, "s3_bucket_name", DEFAULT_S3_BUCKET_NAME)
        s3_region = getattr(settings_service.settings, "s3_region_name", DEFAULT_S3_REGION_NAME)
        s3_access_key = getattr(settings_service.settings, "s3_aws_access_key_id", None)
        s3_secret_key = getattr(settings_service.settings, "s3_aws_secret_access_key", None)
        s3_session_token = getattr(settings_service.settings, "s3_aws_session_token", None)
        s3_role_arn = getattr(settings_service.settings, "s3_role_arn", None)
        self.path = getattr(settings_service.settings, "s3_storage_path", "tenants")

        # Initialize S3 client based on available credentials
        try:
            if s3_access_key and s3_secret_key:
                # Use explicit credentials (access key + secret key)
                self.s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=s3_access_key,
                    aws_secret_access_key=s3_secret_key,
                    aws_session_token=s3_session_token,
                    region_name=s3_region,
                )
                logger.info("S3 client initialized with explicit credentials")
            elif s3_role_arn:
                # Use role-based authentication (IRSA)
                self.s3_client = self._create_role_based_client(s3_role_arn, s3_region)
                logger.info(f"S3 client initialized with role ARN: {s3_role_arn}")
            else:
                # Use default credential chain (environment variables, IAM roles, etc.)
                self.s3_client = boto3.client("s3", region_name=s3_region)
                logger.info("S3 client initialized with default credential chain")
        except (ClientError, NoCredentialsError, FileNotFoundError, PermissionError) as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            # Fallback to a mock client for testing
            self.s3_client = None

        self.set_ready()

    def _create_role_based_client(self, role_arn: str, region: str):
        """Create S3 client using role-based authentication (IRSA)."""
        try:
            # First, assume the role to get temporary credentials
            sts_client = boto3.client("sts", region_name=region)

            # Check if we have a web identity token (for IRSA)
            web_identity_token_file = os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE")
            if web_identity_token_file and Path(web_identity_token_file).exists():
                # IRSA: Use web identity token
                with Path(web_identity_token_file).open() as f:
                    web_identity_token = f.read().strip()

                response = sts_client.assume_role_with_web_identity(
                    RoleArn=role_arn,
                    RoleSessionName="langflow-s3-session",
                    WebIdentityToken=web_identity_token,
                    DurationSeconds=3600,
                )
            else:
                # Regular role assumption
                response = sts_client.assume_role(
                    RoleArn=role_arn, RoleSessionName="langflow-s3-session", DurationSeconds=3600
                )

            credentials = response["Credentials"]

            # Create S3 client with temporary credentials
            return boto3.client(
                "s3",
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                region_name=region,
            )

        except (ClientError, NoCredentialsError, FileNotFoundError, PermissionError) as e:
            logger.error(f"Failed to assume role {role_arn}: {e}")
            # Fallback to default credential chain
            return boto3.client("s3", region_name=region)

    async def save_file(self, flow_id: str, file_name: str, data: bytes) -> None:
        """Save a file to the S3 bucket.

        Args:
            flow_id: The flow ID to save the file under.
            file_name: The name of the file to be saved.
            data: The byte content of the file.

        Raises:
            Exception: If an error occurs during file saving.
        """
        try:
            self.s3_client.put_object(Bucket=self.bucket, Key=f"{self.path}/{flow_id}/{file_name}", Body=data)
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
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=f"{self.path}/{flow_id}/{file_name}")
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
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=f"{self.path}/{flow_id}/")
        except ClientError:
            await logger.aexception(f"Error listing files in flow {flow_id}")
            raise

        files = [
            item["Key"]
            for item in response.get("Contents", [])
            if "/" not in item["Key"][len(f"{self.path}/{flow_id}") :]
        ]
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
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=f"{self.path}/{flow_id}/{file_name}")
            await logger.ainfo(f"File {file_name} deleted successfully from flow {flow_id}.")
        except ClientError:
            await logger.aexception(f"Error deleting file {file_name} from flow {flow_id}")
            raise

    async def teardown(self) -> None:
        """Perform any cleanup operations when the service is being torn down."""
        # No specific teardown actions required for S3 storage at the moment.

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
        try:
            response = self.s3_client.head_object(Bucket=self.bucket, Key=f"{self.path}/{flow_id}/{file_name}")
            file_size = response["ContentLength"]
            await logger.ainfo(f"File {file_name} size retrieved successfully from flow {flow_id}: {file_size} bytes.")
        except ClientError:
            await logger.aexception(f"Error getting file size for {file_name} from flow {flow_id}")
            raise
        else:
            return file_size

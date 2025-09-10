import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from langflow.logging.logger import logger

from .service import StorageService


class S3StorageService(StorageService):
    """A service class for handling operations with AWS S3 storage."""

    def __init__(self, session_service, settings_service) -> None:
        """Initialize the S3 storage service with session and settings services."""
        super().__init__(session_service, settings_service)
        self.bucket = os.getenv("LANGFLOW_S3_BUCKET", "langflow")
        self.s3_client = boto3.client("s3")
        self.set_ready()

    async def save_file(self, flow_id: str, file_name: str, data) -> None:
        """Save a file to the S3 bucket.

        Args:
            flow_id: The folder in the bucket to save the file.
            file_name: The name of the file to be saved.
            data: The byte content of the file.

        Raises:
            Exception: If an error occurs during file saving.
        """
        try:
            self.s3_client.put_object(Bucket=self.bucket, Key=f"{flow_id}/{file_name}", Body=data)
            await logger.ainfo(f"File {file_name} saved successfully in folder {flow_id}.")
        except NoCredentialsError:
            await logger.aexception("Credentials not available for AWS S3.")
            raise
        except ClientError:
            await logger.aexception(f"Error saving file {file_name} in folder {flow_id}")
            raise

    async def get_file(self, flow_id: str, file_name: str):
        """Retrieve a file from the S3 bucket.

        Args:
            flow_id: The folder in the bucket where the file is stored.
            file_name: The name of the file to be retrieved.

        Returns:
            The byte content of the file.

        Raises:
            Exception: If an error occurs during file retrieval.
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=f"{flow_id}/{file_name}")
            await logger.ainfo(f"File {file_name} retrieved successfully from folder {flow_id}.")
            return response["Body"].read()
        except ClientError:
            await logger.aexception(f"Error retrieving file {file_name} from folder {flow_id}")
            raise

    async def list_files(self, flow_id: str):
        """List all files in a specified folder of the S3 bucket.

        Args:
            flow_id: The folder in the bucket to list files from.

        Returns:
            A list of file names.

        Raises:
            Exception: If an error occurs during file listing.
        """
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=str(flow_id))
        except ClientError:
            await logger.aexception(f"Error listing files in folder {flow_id}")
            raise

        files = [item["Key"] for item in response.get("Contents", []) if "/" not in item["Key"][len(flow_id) :]]
        await logger.ainfo(f"{len(files)} files listed in folder {flow_id}.")
        return files

    async def delete_file(self, flow_id: str, file_name: str) -> None:
        """Delete a file from the S3 bucket.

        Args:
            flow_id: The folder in the bucket where the file is stored.
            file_name: The name of the file to be deleted.

        Raises:
            Exception: If an error occurs during file deletion.
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=f"{flow_id}/{file_name}")
            await logger.ainfo(f"File {file_name} deleted successfully from folder {flow_id}.")
        except ClientError:
            await logger.aexception(f"Error deleting file {file_name} from folder {flow_id}")
            raise

    async def teardown(self) -> None:
        """Perform any cleanup operations when the service is being torn down."""
        # No specific teardown actions required for S3 storage at the moment.

    async def get_file_size(self, flow_id: str, file_name: str):
        """Get the size of a file in the S3 bucket."""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket, Key=f"{flow_id}/{file_name}")
            await logger.ainfo(f"File {file_name} retrieved successfully from folder {flow_id}.")
            return response["ContentLength"]
        except ClientError:
            logger.aexception(f"Error getting file size for {file_name} in flow_id {flow_id}: {e}")
            raise

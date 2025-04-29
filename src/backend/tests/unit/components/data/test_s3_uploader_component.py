import os
import tempfile
import uuid
from pathlib import Path

import boto3
import pytest
from langflow.components.amazon.s3_bucket_uploader import S3BucketUploaderComponent
from langflow.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


@pytest.mark.skipif(
    not os.environ.get("AWS_ACCESS_KEY_ID") or not os.environ.get("AWS_SECRET_ACCESS_KEY"),
    reason="Environment variable AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY is not defined.",
)
class TestS3UploaderComponent(ComponentTestBaseWithoutClient):
    """Unit tests for the S3BucketUploaderComponent.

    This test class inherits from ComponentTestBaseWithoutClient and includes several pytest fixtures and a test method
    to verify the functionality of the S3BucketUploaderComponent.

    Fixtures:
        component_class: Returns the component class to be tested.
        file_names_mapping: Returns an empty list since this component doesn't have version-specific files.
        default_kwargs: Returns an empty dictionary since this component doesn't have any default arguments.
        temp_files: Creates three temporary files with predefined content and yields them as Data objects.
        Cleans up the files after the test.
        s3_bucket: Creates a unique S3 bucket for testing, yields the bucket name, and deletes the bucket
        and its contents after the test.

    Test Methods:
        test_upload: Tests the upload functionality of the S3BucketUploaderComponent by uploading temporary files
        to the S3 bucket and verifying their content.
    """

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return S3BucketUploaderComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""

    @pytest.fixture
    def default_kwargs(self):
        """Return an empty dictionary since this component doesn't have any default arguments."""
        return {}

    @pytest.fixture
    def temp_files(self):
        """Setup: Create three temporary files."""
        temp_files = []
        contents = [
            b"Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            b"Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
            b"Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris "
            b"nisi ut aliquip ex ea commodo consequat.",
        ]

        for content in contents:
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
                temp_file.write(content)
                temp_file.flush()
                temp_file.close()
                temp_files.append(temp_file.name)

        data = [
            Data(data={"file_path": file_path, "text": Path(file_path).read_text(encoding="utf-8")})
            for file_path in temp_files
        ]

        yield data

        # Teardown: Explicitly delete the files
        for temp_file in temp_files:
            Path(temp_file).unlink()

    @pytest.fixture
    def s3_bucket(self) -> str:
        """Generate a unique bucket name (AWS requires globally unique names)."""
        bucket_name = f"graphrag-test-bucket-{uuid.uuid4().hex[:8]}"

        # Initialize S3 client using environment variables for credentials
        s3 = boto3.client("s3")

        try:
            # Create an S3 bucket in your default region
            s3.create_bucket(Bucket=bucket_name)

            yield bucket_name

        finally:
            # Teardown: Delete the bucket and its contents
            try:
                # List and delete all objects in the bucket
                objects = s3.list_objects_v2(Bucket=bucket_name).get("Contents", [])
                for obj in objects:
                    s3.delete_object(Bucket=bucket_name, Key=obj["Key"])

                # Delete the bucket
                s3.delete_bucket(Bucket=bucket_name)
            except boto3.exceptions.Boto3Error as e:
                pytest.fail(f"Error during teardown: {e}")

    def test_upload(self, temp_files, s3_bucket):
        """Test uploading files to an S3 bucket."""
        component = S3BucketUploaderComponent()

        # Set AWS credentials from environment variables
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        component.set_attributes(
            {
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key,
                "bucket_name": s3_bucket,
                "strategy": "Store Original File",
                "data_inputs": temp_files,
                "s3_prefix": "test",
                "strip_path": True,
            }
        )

        component.process_files()

        # Check if the files were uploaded. Assumes key and secret are set via environment variables
        s3 = boto3.client("s3")

        for temp_file in temp_files:
            key = f"test/{Path(temp_file.data['file_path']).name}"
            response = s3.get_object(Bucket=s3_bucket, Key=key)
            with Path(temp_file.data["file_path"]).open("rb") as f:
                assert response["Body"].read() == f.read()

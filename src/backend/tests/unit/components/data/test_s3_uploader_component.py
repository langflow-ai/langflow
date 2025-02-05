import os
import tempfile
import uuid

import boto3
import pytest
from langflow.components.data.s3_bucket_uploader import S3BucketUploaderComponent
from langflow.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


class TestS3UploaderComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return S3BucketUploaderComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def temp_files(self):
        # Setup: Create three temporary files
        temp_files = []
        contents = [
            b"Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            b"Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
            b"Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
        ]

        for content in contents:
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
                temp_file.write(content)
                temp_file.flush()
                temp_file.close()
                temp_files.append(temp_file.name)

        data = [Data(data={"file_path": file_path, "text": open(file_path).read()}) for file_path in temp_files]

        yield data

        # Teardown: Explicitly delete the files
        for temp_file in temp_files:
            os.unlink(temp_file)

    @pytest.fixture
    def s3_bucket(self) -> str:
        # Generate a unique bucket name (AWS requires globally unique names)
        bucket_name = f"graphrag-test-bucket-{uuid.uuid4().hex[:8]}"

        # Initialize S3 client using environment variables for credentials. Assumes key and secret are set via environment variables
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
            except Exception as e:
                print(f"Error during teardown: {e}")

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
            key = f"test/{os.path.basename(temp_file.file_path)}"
            print(key)
            response = s3.get_object(Bucket=s3_bucket, Key=key)
            assert response["Body"].read() == open(temp_file.file_path, "rb").read()

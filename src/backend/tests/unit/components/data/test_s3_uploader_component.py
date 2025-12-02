import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langflow.components.amazon.s3_bucket_uploader import S3BucketUploaderComponent
from langflow.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


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
        return []

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
        """Generate a unique bucket name for testing."""
        return f"graphrag-test-bucket-{uuid.uuid4().hex[:8]}"

    def test_upload(self, temp_files, s3_bucket):
        """Test uploading files to an S3 bucket."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        
        with patch("boto3.client", return_value=mock_s3_client):
            component = S3BucketUploaderComponent()

            # Set test credentials and configuration
            component.set_attributes(
                {
                    "aws_access_key_id": "test_key_id",
                    "aws_secret_access_key": "test_secret_key",
                    "bucket_name": s3_bucket,
                    "strategy": "Store Original File",
                    "data_inputs": temp_files,
                    "s3_prefix": "test",
                    "strip_path": True,
                }
            )

            component.process_files()

            # Verify upload_file was called for each temp file
            assert mock_s3_client.upload_file.call_count == len(temp_files)
            
            # Verify the correct keys were used
            for i, temp_file in enumerate(temp_files):
                expected_key = f"test/{Path(temp_file.data['file_path']).name}"
                call_args = mock_s3_client.upload_file.call_args_list[i]
                # upload_file(Filename, Bucket, Key)
                assert call_args[1]["Bucket"] == s3_bucket
                assert call_args[1]["Key"] == expected_key

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from langflow.services.storage.s3 import S3StorageService


class TestS3StorageService:
    """Test cases for S3StorageService."""

    @pytest.fixture
    def mock_session_service(self):
        """Create a mock session service."""
        return MagicMock()

    @pytest.fixture
    def mock_settings_service(self):
        """Create a mock settings service."""
        return MagicMock()

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        return MagicMock()

    @pytest.fixture
    def s3_service(self, mock_session_service, mock_settings_service, mock_s3_client):
        """Create an S3StorageService instance for testing."""
        with patch("langflow.services.storage.s3.boto3.client", return_value=mock_s3_client):
            return S3StorageService(mock_session_service, mock_settings_service)

    def test_initialization(self, mock_session_service, mock_settings_service, mock_s3_client):
        """Test proper initialization of S3StorageService."""
        with patch("langflow.services.storage.s3.boto3.client", return_value=mock_s3_client) as mock_boto_client:
            service = S3StorageService(mock_session_service, mock_settings_service)

            mock_boto_client.assert_called_once_with("s3")
            assert service.bucket == "langflow"
            assert service.s3_client == mock_s3_client

    def test_bucket_name(self, s3_service):
        """Test that bucket name is set correctly."""
        assert s3_service.bucket == "langflow"

    @pytest.mark.asyncio
    async def test_save_file_success(self, s3_service):
        """Test successful file saving to S3."""
        folder = "test_folder"
        file_name = "test_file.txt"
        data = b"test file content"

        await s3_service.save_file(folder, file_name, data)

        s3_service.s3_client.put_object.assert_called_once_with(
            Bucket="langflow", Key=f"{folder}/{file_name}", Body=data
        )

    @pytest.mark.asyncio
    async def test_save_file_with_nested_folder(self, s3_service):
        """Test saving file with nested folder structure."""
        folder = "parent/child/grandchild"
        file_name = "nested_file.json"
        data = b'{"key": "value"}'

        await s3_service.save_file(folder, file_name, data)

        s3_service.s3_client.put_object.assert_called_once_with(
            Bucket="langflow", Key=f"{folder}/{file_name}", Body=data
        )

    @pytest.mark.asyncio
    async def test_save_file_client_error(self, s3_service):
        """Test save_file handling ClientError."""
        s3_service.s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject"
        )

        folder = "test_folder"
        file_name = "test_file.txt"
        data = b"test content"

        with pytest.raises(ClientError):
            await s3_service.save_file(folder, file_name, data)

    @pytest.mark.asyncio
    async def test_save_file_no_credentials_error(self, s3_service):
        """Test save_file handling NoCredentialsError."""
        s3_service.s3_client.put_object.side_effect = NoCredentialsError()

        folder = "test_folder"
        file_name = "test_file.txt"
        data = b"test content"

        with pytest.raises(ClientError):
            await s3_service.save_file(folder, file_name, data)

    def test_inheritance(self, s3_service):
        """Test that S3StorageService properly inherits from StorageService."""
        from langflow.services.storage.service import StorageService

        assert isinstance(s3_service, StorageService)

    @pytest.mark.asyncio
    async def test_save_file_empty_data(self, s3_service):
        """Test saving file with empty data."""
        folder = "test_folder"
        file_name = "empty_file.txt"
        data = b""

        await s3_service.save_file(folder, file_name, data)

        s3_service.s3_client.put_object.assert_called_once_with(
            Bucket="langflow", Key=f"{folder}/{file_name}", Body=data
        )

    @pytest.mark.asyncio
    async def test_save_file_large_data(self, s3_service):
        """Test saving file with large data."""
        folder = "test_folder"
        file_name = "large_file.bin"
        data = b"x" * (10 * 1024 * 1024)  # 10MB of data

        await s3_service.save_file(folder, file_name, data)

        s3_service.s3_client.put_object.assert_called_once_with(
            Bucket="langflow", Key=f"{folder}/{file_name}", Body=data
        )

    @pytest.mark.asyncio
    async def test_save_file_logs_errors(self, s3_service):
        """Test that errors are properly logged."""
        s3_service.s3_client.put_object.side_effect = Exception("Test error")

        folder = "test_folder"
        file_name = "test_file.txt"
        data = b"test content"

        with pytest.raises(ClientError):
            await s3_service.save_file(folder, file_name, data)

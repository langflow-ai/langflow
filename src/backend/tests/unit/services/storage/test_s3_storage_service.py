"""Unit tests for S3StorageService."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from lfx.services.storage.s3 import S3StorageService


class TestS3StorageService:
    """Test cases for S3StorageService."""

    @pytest.fixture
    def mock_session_service(self):
        """Create a mock session service."""
        return MagicMock()

    @pytest.fixture
    def mock_settings_service(self):
        """Create a mock settings service with object storage configuration."""
        mock_settings = MagicMock()
        mock_settings.storage_type = "s3"  # Set storage type to S3
        mock_settings.object_storage_bucket_name = "test-bucket"
        mock_settings.object_storage_prefix = "tenants"
        mock_settings.object_storage_tags = None

        mock_service = MagicMock()
        mock_service.settings = mock_settings
        return mock_service

    @pytest.fixture
    def s3_service(self, mock_session_service, mock_settings_service):
        """Create an S3StorageService instance with mocked dependencies."""
        with patch("boto3.client") as mock_boto_client:
            mock_s3_client = MagicMock()
            mock_boto_client.return_value = mock_s3_client

            service = S3StorageService(settings_service=mock_settings_service)
            service.s3_client = mock_s3_client
            return service

    @pytest.fixture
    def s3_service_no_client(self, mock_settings_service):
        """Create an S3StorageService instance with no S3 client (initialization failed)."""
        with patch("boto3.client", side_effect=Exception("Failed to initialize")):
            try:
                service = S3StorageService(settings_service=mock_settings_service)
            except Exception:
                service = S3StorageService.__new__(S3StorageService)
                service.bucket_name = "test-bucket"
                service.object_prefix = "tenants"
                service.tags = None
                service.s3_client = None
        return service

    @pytest.fixture
    def test_data(self):
        """Create test file data."""
        return b"Hello, World! This is test file content."

    @pytest.fixture
    def test_flow_id(self):
        """Create a test flow ID."""
        return str(uuid4())

    @pytest.fixture
    def test_file_name(self):
        """Create a test file name."""
        return "test_file.txt"

    # Test initialization
    def test_init_success(self, mock_settings_service):
        """Test S3StorageService initialization success."""
        with patch("boto3.client") as mock_boto_client:
            mock_s3_client = MagicMock()
            mock_boto_client.return_value = mock_s3_client

            service = S3StorageService(settings_service=mock_settings_service)

            assert service.bucket_name == "test-bucket"
            assert service.object_prefix == "tenants"
            assert service.tags is None
            assert service.s3_client == mock_s3_client
            mock_boto_client.assert_called_once_with("s3")

    def test_init_with_tags(self):
        """Test S3StorageService initialization with tags."""
        mock_settings = MagicMock()
        mock_settings.object_storage_bucket_name = "test-bucket"
        mock_settings.object_storage_prefix = "tenants"
        mock_settings.object_storage_tags = {"env": "test", "team": "langflow"}

        mock_service = MagicMock()
        mock_service.settings = mock_settings

        with patch("boto3.client") as mock_boto_client:
            mock_s3_client = MagicMock()
            mock_boto_client.return_value = mock_s3_client

            service = S3StorageService(settings_service=mock_service)

            assert service.bucket_name == "test-bucket"
            assert service.object_prefix == "tenants"
            assert service.tags == {"env": "test", "team": "langflow"}

    def test_init_missing_bucket(self):
        """Test S3StorageService initialization with missing bucket name."""
        mock_settings = MagicMock()
        mock_settings.object_storage_bucket_name = None
        mock_settings.object_storage_prefix = "tenants"
        mock_settings.object_storage_tags = None

        mock_service = MagicMock()
        mock_service.settings = mock_settings

        with pytest.raises(ValueError, match="Object storage bucket name is required"):
            S3StorageService(settings_service=mock_service)

    def test_init_failure_raises_exception(self, mock_settings_service):
        """Test S3StorageService initialization failure raises exception."""
        with (
            patch(
                "boto3.client",
                side_effect=ClientError({"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "AssumeRole"),
            ),
            pytest.raises(ClientError),
        ):
            S3StorageService(settings_service=mock_settings_service)

    # Test save_file method
    @pytest.mark.asyncio
    async def test_save_file_success(self, s3_service, test_data, test_flow_id, test_file_name):
        """Test successful file save."""
        await s3_service.save_file(test_flow_id, test_file_name, test_data)

        s3_service.s3_client.put_object.assert_called_once_with(
            Bucket="test-bucket", Key=f"tenants/{test_flow_id}/{test_file_name}", Body=test_data
        )

    @pytest.mark.asyncio
    async def test_save_file_with_tags(self, test_data, test_flow_id, test_file_name):
        """Test file save with tags."""
        mock_settings = MagicMock()
        mock_settings.object_storage_bucket_name = "test-bucket"
        mock_settings.object_storage_prefix = "tenants"
        mock_settings.object_storage_tags = {"env": "test", "team": "langflow"}

        mock_service = MagicMock()
        mock_service.settings = mock_settings

        with patch("boto3.client") as mock_boto_client:
            mock_s3_client = MagicMock()
            mock_boto_client.return_value = mock_s3_client

            service = S3StorageService(settings_service=mock_service)
            await service.save_file(test_flow_id, test_file_name, test_data)

            mock_s3_client.put_object.assert_called_once_with(
                Bucket="test-bucket",
                Key=f"tenants/{test_flow_id}/{test_file_name}",
                Body=test_data,
                Tagging="env=test&team=langflow",
            )

    @pytest.mark.asyncio
    async def test_save_file_invalid_data_type(self, s3_service, test_flow_id, test_file_name):
        """Test save_file with invalid data type."""
        with pytest.raises(TypeError, match="Expected bytes, got"):
            await s3_service.save_file(test_flow_id, test_file_name, "not bytes")

    @pytest.mark.asyncio
    async def test_save_file_no_client(self, s3_service_no_client, test_data, test_flow_id, test_file_name):
        """Test save_file when S3 client is not initialized."""
        with pytest.raises(RuntimeError, match="S3 client not initialized"):
            await s3_service_no_client.save_file(test_flow_id, test_file_name, test_data)

    @pytest.mark.asyncio
    async def test_save_file_no_credentials_error(self, s3_service, test_data, test_flow_id, test_file_name):
        """Test save_file with NoCredentialsError."""
        s3_service.s3_client.put_object.side_effect = NoCredentialsError()

        with pytest.raises(NoCredentialsError):
            await s3_service.save_file(test_flow_id, test_file_name, test_data)

    @pytest.mark.asyncio
    async def test_save_file_client_error(self, s3_service, test_data, test_flow_id, test_file_name):
        """Test save_file with ClientError."""
        s3_service.s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject"
        )

        with pytest.raises(ClientError):
            await s3_service.save_file(test_flow_id, test_file_name, test_data)

    # Test get_file method
    @pytest.mark.asyncio
    async def test_get_file_success(self, s3_service, test_data, test_flow_id, test_file_name):
        """Test successful file retrieval."""
        mock_response = {"Body": MagicMock()}
        mock_response["Body"].read.return_value = test_data
        s3_service.s3_client.get_object.return_value = mock_response

        result = await s3_service.get_file(test_flow_id, test_file_name)

        assert result == test_data
        s3_service.s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key=f"tenants/{test_flow_id}/{test_file_name}"
        )

    @pytest.mark.asyncio
    async def test_get_file_no_client(self, s3_service_no_client, test_flow_id, test_file_name):
        """Test get_file when S3 client is not initialized."""
        with pytest.raises(RuntimeError, match="S3 client not initialized"):
            await s3_service_no_client.get_file(test_flow_id, test_file_name)

    @pytest.mark.asyncio
    async def test_get_file_client_error(self, s3_service, test_flow_id, test_file_name):
        """Test get_file with ClientError."""
        s3_service.s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist"}}, "GetObject"
        )

        with pytest.raises(ClientError):
            await s3_service.get_file(test_flow_id, test_file_name)

    # Test list_files method
    @pytest.mark.asyncio
    async def test_list_files_success(self, s3_service, test_flow_id):
        """Test successful file listing."""
        mock_response = {
            "Contents": [
                {"Key": f"tenants/{test_flow_id}/file1.txt"},
                {"Key": f"tenants/{test_flow_id}/file2.txt"},
                {"Key": f"tenants/{test_flow_id}/subdir/file3.txt"},  # Should be filtered out
                {"Key": f"tenants/{test_flow_id}/file4.txt"},
            ]
        }
        s3_service.s3_client.list_objects_v2.return_value = mock_response

        result = await s3_service.list_files(test_flow_id)

        # The implementation filters out files with "/" in the part after the prefix
        # So subdir/file3.txt should be filtered out
        expected_files = [
            f"tenants/{test_flow_id}/file1.txt",
            f"tenants/{test_flow_id}/file2.txt",
            f"tenants/{test_flow_id}/file4.txt",
        ]
        assert result == expected_files
        s3_service.s3_client.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket", Prefix=f"tenants/{test_flow_id}/"
        )

    @pytest.mark.asyncio
    async def test_list_files_empty(self, s3_service, test_flow_id):
        """Test file listing with no files."""
        mock_response = {"Contents": []}
        s3_service.s3_client.list_objects_v2.return_value = mock_response

        result = await s3_service.list_files(test_flow_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_list_files_no_client(self, s3_service_no_client, test_flow_id):
        """Test list_files when S3 client is not initialized."""
        with pytest.raises(RuntimeError, match="S3 client not initialized"):
            await s3_service_no_client.list_files(test_flow_id)

    @pytest.mark.asyncio
    async def test_list_files_client_error(self, s3_service, test_flow_id):
        """Test list_files with ClientError."""
        s3_service.s3_client.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "ListObjectsV2"
        )

        with pytest.raises(ClientError):
            await s3_service.list_files(test_flow_id)

    # Test delete_file method
    @pytest.mark.asyncio
    async def test_delete_file_success(self, s3_service, test_flow_id, test_file_name):
        """Test successful file deletion."""
        await s3_service.delete_file(test_flow_id, test_file_name)

        s3_service.s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key=f"tenants/{test_flow_id}/{test_file_name}"
        )

    @pytest.mark.asyncio
    async def test_delete_file_no_client(self, s3_service_no_client, test_flow_id, test_file_name):
        """Test delete_file when S3 client is not initialized."""
        with pytest.raises(RuntimeError, match="S3 client not initialized"):
            await s3_service_no_client.delete_file(test_flow_id, test_file_name)

    @pytest.mark.asyncio
    async def test_delete_file_client_error(self, s3_service, test_flow_id, test_file_name):
        """Test delete_file with ClientError."""
        s3_service.s3_client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist"}}, "DeleteObject"
        )

        with pytest.raises(ClientError):
            await s3_service.delete_file(test_flow_id, test_file_name)

    # Test get_file_size method
    @pytest.mark.asyncio
    async def test_get_file_size_success(self, s3_service, test_flow_id, test_file_name):
        """Test successful file size retrieval."""
        mock_response = {"ContentLength": 1024}
        s3_service.s3_client.head_object.return_value = mock_response

        result = await s3_service.get_file_size(test_flow_id, test_file_name)

        assert result == 1024
        s3_service.s3_client.head_object.assert_called_once_with(
            Bucket="test-bucket", Key=f"tenants/{test_flow_id}/{test_file_name}"
        )

    @pytest.mark.asyncio
    async def test_get_file_size_no_client(self, s3_service_no_client, test_flow_id, test_file_name):
        """Test get_file_size when S3 client is not initialized."""
        with pytest.raises(RuntimeError, match="S3 client not initialized"):
            await s3_service_no_client.get_file_size(test_flow_id, test_file_name)

    @pytest.mark.asyncio
    async def test_get_file_size_client_error(self, s3_service, test_flow_id, test_file_name):
        """Test get_file_size with ClientError."""
        s3_service.s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist"}}, "HeadObject"
        )

        with pytest.raises(ClientError):
            await s3_service.get_file_size(test_flow_id, test_file_name)

    # Test teardown method
    @pytest.mark.asyncio
    async def test_teardown(self, s3_service):
        """Test teardown method."""
        # Should not raise any exceptions
        await s3_service.teardown()

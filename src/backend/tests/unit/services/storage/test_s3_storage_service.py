"""Unit tests for S3StorageService."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

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
        """Create a mock settings service with S3 configuration."""
        mock_settings = MagicMock()
        mock_settings.storage_type = "s3"  # Set storage type to S3
        mock_settings.s3_bucket_name = "test-bucket"
        mock_settings.s3_region_name = "us-east-1"
        mock_settings.s3_aws_access_key_id = "test-access-key"
        mock_settings.s3_aws_secret_access_key = "test-secret-key"  # noqa: S105
        mock_settings.s3_aws_session_token = None
        mock_settings.s3_role_arn = None
        mock_settings.s3_storage_path = "tenants"

        mock_service = MagicMock()
        mock_service.settings = mock_settings
        return mock_service

    @pytest.fixture
    def s3_service(self, mock_session_service, mock_settings_service):
        """Create an S3StorageService instance with mocked dependencies."""
        with patch("boto3.client") as mock_boto_client:
            mock_s3_client = MagicMock()
            mock_boto_client.return_value = mock_s3_client

            service = S3StorageService(mock_session_service, mock_settings_service)
            service.s3_client = mock_s3_client
            return service

    @pytest.fixture
    def s3_service_no_client(self, mock_session_service, mock_settings_service):
        """Create an S3StorageService instance with no S3 client (initialization failed)."""
        service = S3StorageService(mock_session_service, mock_settings_service)
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
    def test_init_with_credentials(self, mock_session_service, mock_settings_service):
        """Test S3StorageService initialization with explicit credentials."""
        with patch("boto3.client") as mock_boto_client:
            mock_s3_client = MagicMock()
            mock_boto_client.return_value = mock_s3_client

            service = S3StorageService(mock_session_service, mock_settings_service)

            assert service.bucket == "test-bucket"
            assert service.path == "tenants"
            assert service.s3_client == mock_s3_client
            mock_boto_client.assert_called_once_with(
                "s3",
                aws_access_key_id="test-access-key",
                aws_secret_access_key="test-secret-key",  # noqa: S106
                aws_session_token=None,
                region_name="us-east-1",
            )

    def test_init_with_role_arn(self, mock_session_service):
        """Test S3StorageService initialization with role ARN."""
        mock_settings = MagicMock()
        mock_settings.s3_bucket_name = "test-bucket"
        mock_settings.s3_region_name = "us-east-1"
        mock_settings.s3_aws_access_key_id = None
        mock_settings.s3_aws_secret_access_key = None
        mock_settings.s3_aws_session_token = None
        mock_settings.s3_role_arn = "arn:aws:iam::123456789012:role/test-role"
        mock_settings.s3_storage_path = "tenants"

        mock_service = MagicMock()
        mock_service.settings = mock_settings

        with (
            patch("boto3.client"),
            patch.object(S3StorageService, "_create_role_based_client") as mock_create_role,
        ):
            mock_s3_client = MagicMock()
            mock_create_role.return_value = mock_s3_client

            service = S3StorageService(mock_session_service, mock_service)

            assert service.bucket == "test-bucket"
            assert service.path == "tenants"
            mock_create_role.assert_called_once_with("arn:aws:iam::123456789012:role/test-role", "us-east-1")

    def test_init_with_default_credentials(self, mock_session_service):
        """Test S3StorageService initialization with default credential chain."""
        mock_settings = MagicMock()
        mock_settings.s3_bucket_name = "test-bucket"
        mock_settings.s3_region_name = "us-east-1"
        mock_settings.s3_aws_access_key_id = None
        mock_settings.s3_aws_secret_access_key = None
        mock_settings.s3_aws_session_token = None
        mock_settings.s3_role_arn = None
        mock_settings.s3_storage_path = "tenants"

        mock_service = MagicMock()
        mock_service.settings = mock_settings

        with patch("boto3.client") as mock_boto_client:
            mock_s3_client = MagicMock()
            mock_boto_client.return_value = mock_s3_client

            service = S3StorageService(mock_session_service, mock_service)

            assert service.bucket == "test-bucket"
            assert service.path == "tenants"
            assert service.s3_client == mock_s3_client
            mock_boto_client.assert_called_once_with("s3", region_name="us-east-1")

    def test_init_failure_fallback(self, mock_session_service, mock_settings_service):
        """Test S3StorageService initialization failure with fallback."""
        with patch(
            "boto3.client",
            side_effect=ClientError({"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "AssumeRole"),
        ):
            service = S3StorageService(mock_session_service, mock_settings_service)

            assert service.bucket == "test-bucket"
            assert service.path == "tenants"
            assert service.s3_client is None

    # Test save_file method
    @pytest.mark.asyncio
    async def test_save_file_success(self, s3_service, test_data, test_flow_id, test_file_name):
        """Test successful file save."""
        await s3_service.save_file(test_flow_id, test_file_name, test_data)

        s3_service.s3_client.put_object.assert_called_once_with(
            Bucket="test-bucket", Key=f"tenants/{test_flow_id}/{test_file_name}", Body=test_data
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

    # Test role-based client creation
    def test_create_role_based_client_with_web_identity(self, s3_service):
        """Test role-based client creation with web identity token."""
        with (
            patch("os.getenv", return_value="/var/run/secrets/aws-eks-token/token"),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open", mock_open(read_data="test-token")),
            patch("boto3.client") as mock_boto_client,
        ):
            mock_sts_client = MagicMock()
            mock_s3_client = MagicMock()
            mock_boto_client.side_effect = [mock_sts_client, mock_s3_client]

            mock_sts_client.assume_role_with_web_identity.return_value = {
                "Credentials": {
                    "AccessKeyId": "temp-access-key",
                    "SecretAccessKey": "temp-secret-key",
                    "SessionToken": "temp-session-token",
                }
            }

            result = s3_service._create_role_based_client("arn:aws:iam::123456789012:role/test-role", "us-east-1")

            assert result == mock_s3_client
            mock_sts_client.assume_role_with_web_identity.assert_called_once_with(
                RoleArn="arn:aws:iam::123456789012:role/test-role",
                RoleSessionName="langflow-s3-session",
                WebIdentityToken="test-token",
                DurationSeconds=3600,
            )

    def test_create_role_based_client_without_web_identity(self, s3_service):
        """Test role-based client creation without web identity token."""
        with patch("os.getenv", return_value=None), patch("boto3.client") as mock_boto_client:
            mock_sts_client = MagicMock()
            mock_s3_client = MagicMock()
            mock_boto_client.side_effect = [mock_sts_client, mock_s3_client]

            mock_sts_client.assume_role.return_value = {
                "Credentials": {
                    "AccessKeyId": "temp-access-key",
                    "SecretAccessKey": "temp-secret-key",
                    "SessionToken": "temp-session-token",
                }
            }

            result = s3_service._create_role_based_client("arn:aws:iam::123456789012:role/test-role", "us-east-1")

            assert result == mock_s3_client
            mock_sts_client.assume_role.assert_called_once_with(
                RoleArn="arn:aws:iam::123456789012:role/test-role",
                RoleSessionName="langflow-s3-session",
                DurationSeconds=3600,
            )

    def test_create_role_based_client_failure(self, s3_service):
        """Test role-based client creation failure with fallback."""
        with patch("os.getenv", return_value=None), patch("boto3.client") as mock_boto_client:
            mock_sts_client = MagicMock()
            mock_s3_client = MagicMock()
            mock_boto_client.side_effect = [mock_sts_client, mock_s3_client]

            mock_sts_client.assume_role.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "AssumeRole"
            )

            result = s3_service._create_role_based_client("arn:aws:iam::123456789012:role/test-role", "us-east-1")

            assert result == mock_s3_client
            mock_boto_client.assert_called_with("s3", region_name="us-east-1")


def mock_open(read_data):
    """Helper function to mock file opening."""
    from unittest.mock import mock_open as _mock_open

    return _mock_open(read_data=read_data)

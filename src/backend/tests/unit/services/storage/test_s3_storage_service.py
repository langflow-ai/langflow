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

    # Tests for new unified storage methods
    # Test is_remote_path method
    def test_is_remote_path_true(self, s3_service):
        """Test is_remote_path returns True for S3 URIs."""
        assert s3_service.is_remote_path("s3://bucket/prefix/flow/file.txt") is True
        assert s3_service.is_remote_path("s3://my-bucket/test.pdf") is True

    def test_is_remote_path_false(self, s3_service):
        """Test is_remote_path returns False for non-S3 paths."""
        assert s3_service.is_remote_path("/local/path/file.txt") is False
        assert s3_service.is_remote_path("relative/path.txt") is False
        assert s3_service.is_remote_path("") is False

    def test_is_remote_path_invalid_type(self, s3_service):
        """Test is_remote_path handles non-string input."""
        assert s3_service.is_remote_path(None) is False
        assert s3_service.is_remote_path(123) is False

    # Test parse_path method
    def test_parse_path_valid_s3_uri(self, s3_service):
        """Test parsing valid S3 URI."""
        flow_id, file_name = s3_service.parse_path("s3://bucket/prefix/flow-123/document.pdf")

        assert flow_id == "flow-123"
        assert file_name == "document.pdf"

    def test_parse_path_complex_s3_uri(self, s3_service):
        """Test parsing S3 URI with multiple prefix levels."""
        flow_id, file_name = s3_service.parse_path("s3://my-bucket/tenants/org1/flow-456/report.xlsx")

        assert flow_id == "flow-456"
        assert file_name == "report.xlsx"

    def test_parse_path_non_s3_uri(self, s3_service):
        """Test parsing non-S3 path returns None."""
        assert s3_service.parse_path("/local/path/file.txt") is None
        assert s3_service.parse_path("relative/file.txt") is None

    def test_parse_path_invalid_s3_uri(self, s3_service):
        """Test parsing invalid S3 URI returns None."""
        # Too few path components
        assert s3_service.parse_path("s3://bucket/file.txt") is None
        assert s3_service.parse_path("s3://bucket") is None
        assert s3_service.parse_path("s3://") is None

    def test_parse_path_empty_string(self, s3_service):
        """Test parsing empty string returns None."""
        assert s3_service.parse_path("") is None

    # Test path_exists method
    @pytest.mark.asyncio
    async def test_path_exists_true(self, s3_service, test_flow_id, test_file_name):
        """Test path_exists returns True when file exists."""
        s3_service.s3_client.head_object.return_value = {"ContentLength": 100}

        exists = await s3_service.path_exists(test_flow_id, test_file_name)

        assert exists is True
        s3_service.s3_client.head_object.assert_called_once_with(
            Bucket="test-bucket", Key=f"tenants/{test_flow_id}/{test_file_name}"
        )

    @pytest.mark.asyncio
    async def test_path_exists_false_404(self, s3_service, test_flow_id, test_file_name):
        """Test path_exists returns False when file doesn't exist (404)."""
        s3_service.s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )

        exists = await s3_service.path_exists(test_flow_id, test_file_name)

        assert exists is False

    @pytest.mark.asyncio
    async def test_path_exists_no_client(self, s3_service_no_client, test_flow_id, test_file_name):
        """Test path_exists raises error when S3 client not initialized."""
        with pytest.raises(RuntimeError, match="S3 client not initialized"):
            await s3_service_no_client.path_exists(test_flow_id, test_file_name)

    @pytest.mark.asyncio
    async def test_path_exists_other_error(self, s3_service, test_flow_id, test_file_name):
        """Test path_exists raises error for non-404 errors."""
        s3_service.s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "HeadObject"
        )

        with pytest.raises(ClientError):
            await s3_service.path_exists(test_flow_id, test_file_name)

    # Test read_file method
    @pytest.mark.asyncio
    async def test_read_file_success(self, s3_service, test_data):
        """Test reading file through unified interface."""
        s3_uri = "s3://bucket/prefix/flow-789/document.pdf"

        mock_body = MagicMock()
        mock_body.read.return_value = test_data
        s3_service.s3_client.get_object.return_value = {"Body": mock_body}

        content = await s3_service.read_file(s3_uri)

        assert content == test_data
        s3_service.s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="tenants/flow-789/document.pdf"
        )

    @pytest.mark.asyncio
    async def test_read_file_invalid_uri(self, s3_service):
        """Test reading file with invalid S3 URI raises ValueError."""
        with pytest.raises(ValueError, match="Invalid S3 URI format"):
            await s3_service.read_file("s3://bucket/file.txt")

    @pytest.mark.asyncio
    async def test_read_file_non_s3_uri(self, s3_service):
        """Test reading file with non-S3 path raises ValueError."""
        with pytest.raises(ValueError, match="Invalid S3 URI format"):
            await s3_service.read_file("/local/path/file.txt")

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, s3_service):
        """Test reading non-existent file raises appropriate error."""
        s3_uri = "s3://bucket/prefix/flow-123/nonexistent.txt"

        s3_service.s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist"}}, "GetObject"
        )

        with pytest.raises(ClientError):
            await s3_service.read_file(s3_uri)

    # Test write_file method
    @pytest.mark.asyncio
    async def test_write_file_with_s3_uri(self, s3_service, test_data):
        """Test writing file with S3 URI."""
        s3_uri = "s3://bucket/prefix/flow-abc/new.txt"

        result = await s3_service.write_file(s3_uri, test_data)

        assert result == s3_uri
        s3_service.s3_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_file_with_explicit_flow_id(self, s3_service, test_data):
        """Test writing file with explicit flow_id parameter."""
        result = await s3_service.write_file("document.pdf", test_data, flow_id="my-flow")

        expected_uri = "s3://test-bucket/tenants/my-flow/document.pdf"
        assert result == expected_uri
        s3_service.s3_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_file_extracts_filename_from_s3_uri(self, s3_service, test_data):
        """Test writing file extracts filename correctly from S3 URI."""
        s3_uri = "s3://bucket/prefix/flow-123/report.pdf"

        await s3_service.write_file(s3_uri, test_data, flow_id="override-flow")

        # Should use override flow_id but keep filename from URI
        expected_uri = "s3://test-bucket/tenants/override-flow/report.pdf"
        result = s3_service.s3_client.put_object.call_args[1]
        assert "tenants/override-flow/report.pdf" in result["Key"]

    @pytest.mark.asyncio
    async def test_write_file_without_flow_id_non_s3_path(self, s3_service, test_data):
        """Test writing file without flow_id and non-S3 path raises ValueError."""
        with pytest.raises(ValueError, match="flow_id must be provided"):
            await s3_service.write_file("local/file.txt", test_data)

    @pytest.mark.asyncio
    async def test_write_file_invalid_s3_uri(self, s3_service, test_data):
        """Test writing file with invalid S3 URI raises ValueError."""
        with pytest.raises(ValueError, match="Invalid S3 URI format"):
            await s3_service.write_file("s3://bucket/file.txt", test_data)

    @pytest.mark.asyncio
    async def test_write_file_empty_content(self, s3_service):
        """Test writing empty file."""
        result = await s3_service.write_file("empty.txt", b"", flow_id="test-flow")

        expected_uri = "s3://test-bucket/tenants/test-flow/empty.txt"
        assert result == expected_uri

    # Integration tests combining multiple new methods
    @pytest.mark.asyncio
    async def test_workflow_parse_write_check_read(self, s3_service, test_data):
        """Test complete workflow: parse, write, check, read."""
        s3_uri = "s3://bucket/prefix/integration-flow/workflow.txt"

        # Parse the URI
        flow_id, file_name = s3_service.parse_path(s3_uri)
        assert flow_id == "integration-flow"
        assert file_name == "workflow.txt"

        # Write the file
        mock_body = MagicMock()
        mock_body.read.return_value = test_data
        s3_service.s3_client.get_object.return_value = {"Body": mock_body}
        s3_service.s3_client.head_object.return_value = {"ContentLength": len(test_data)}

        result_uri = await s3_service.write_file(s3_uri, test_data)
        assert "integration-flow/workflow.txt" in result_uri

        # Check existence
        exists = await s3_service.path_exists(flow_id, file_name)
        assert exists is True

        # Read back
        content = await s3_service.read_file(s3_uri)
        assert content == test_data

    def test_is_remote_path_consistency(self, s3_service):
        """Test is_remote_path is consistent with parse_path."""
        s3_paths = [
            "s3://bucket/prefix/flow/file.txt",
            "s3://my-bucket/tenants/org/flow-123/doc.pdf",
        ]
        local_paths = ["/local/path.txt", "relative/file.txt", ""]

        for path in s3_paths:
            assert s3_service.is_remote_path(path) is True
            assert s3_service.parse_path(path) is not None

        for path in local_paths:
            assert s3_service.is_remote_path(path) is False
            assert s3_service.parse_path(path) is None

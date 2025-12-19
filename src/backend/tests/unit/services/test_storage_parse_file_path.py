"""Tests for storage service parse_file_path method."""

from unittest.mock import Mock

from langflow.services.storage.local import LocalStorageService
from langflow.services.storage.s3 import S3StorageService


class TestLocalStorageParseFilePath:
    """Test LocalStorageService.parse_file_path method."""

    def test_parse_with_data_dir(self):
        """Test parsing path that includes data_dir."""
        # Mock the services
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        # Test with full path including data_dir
        flow_id, file_name = service.parse_file_path("/data/user_123/image.png")
        assert flow_id == "user_123"
        assert file_name == "image.png"

    def test_parse_without_data_dir(self):
        """Test parsing path without data_dir."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        # Test with relative path (no data_dir)
        flow_id, file_name = service.parse_file_path("user_123/image.png")
        assert flow_id == "user_123"
        assert file_name == "image.png"

    def test_parse_nested_flow_id(self):
        """Test parsing path with nested flow_id."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        # Test with nested flow_id
        flow_id, file_name = service.parse_file_path("/data/bucket/user_123/image.png")
        assert flow_id == "bucket/user_123"
        assert file_name == "image.png"

    def test_parse_just_filename(self):
        """Test parsing just a filename with no directory."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        # Test with just filename
        flow_id, file_name = service.parse_file_path("image.png")
        assert flow_id == ""
        assert file_name == "image.png"


class TestS3StorageParseFilePath:
    """Test S3StorageService.parse_file_path method."""

    def test_parse_with_prefix(self):
        """Test parsing path that includes S3 prefix."""
        # Mock the services
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"
        mock_settings.settings.object_storage_bucket_name = "test-bucket"
        mock_settings.settings.object_storage_prefix = "files/"
        mock_settings.settings.object_storage_tags = {}

        service = S3StorageService(mock_session, mock_settings)

        # Test with full path including prefix
        flow_id, file_name = service.parse_file_path("files/user_123/image.png")
        assert flow_id == "user_123"
        assert file_name == "image.png"

    def test_parse_without_prefix(self):
        """Test parsing path without S3 prefix."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"
        mock_settings.settings.object_storage_bucket_name = "test-bucket"
        mock_settings.settings.object_storage_prefix = "files/"
        mock_settings.settings.object_storage_tags = {}

        service = S3StorageService(mock_session, mock_settings)

        # Test with relative path (no prefix)
        flow_id, file_name = service.parse_file_path("user_123/image.png")
        assert flow_id == "user_123"
        assert file_name == "image.png"

    def test_parse_nested_flow_id(self):
        """Test parsing path with nested flow_id."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"
        mock_settings.settings.object_storage_bucket_name = "test-bucket"
        mock_settings.settings.object_storage_prefix = "files-test-1/"
        mock_settings.settings.object_storage_tags = {}

        service = S3StorageService(mock_session, mock_settings)

        # Test with nested flow_id (real-world example from logs)
        flow_id, file_name = service.parse_file_path(
            "files-test-1/afffa27a-a9f0-4511-b1a9-7e6cb2b3df05/2025-12-07_14-47-29_langflow_pid_mem_usage.png"
        )
        assert flow_id == "afffa27a-a9f0-4511-b1a9-7e6cb2b3df05"
        assert file_name == "2025-12-07_14-47-29_langflow_pid_mem_usage.png"

    def test_parse_nested_flow_id_without_prefix(self):
        """Test parsing nested flow_id without prefix."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"
        mock_settings.settings.object_storage_bucket_name = "test-bucket"
        mock_settings.settings.object_storage_prefix = "files-test-1/"
        mock_settings.settings.object_storage_tags = {}

        service = S3StorageService(mock_session, mock_settings)

        # Test without prefix (as seen in error logs)
        flow_id, file_name = service.parse_file_path(
            "afffa27a-a9f0-4511-b1a9-7e6cb2b3df05/2025-12-07_14-47-29_langflow_pid_mem_usage.png"
        )
        assert flow_id == "afffa27a-a9f0-4511-b1a9-7e6cb2b3df05"
        assert file_name == "2025-12-07_14-47-29_langflow_pid_mem_usage.png"

    def test_parse_just_filename(self):
        """Test parsing just a filename with no directory."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"
        mock_settings.settings.object_storage_bucket_name = "test-bucket"
        mock_settings.settings.object_storage_prefix = "files/"
        mock_settings.settings.object_storage_tags = {}

        service = S3StorageService(mock_session, mock_settings)

        # Test with just filename
        flow_id, file_name = service.parse_file_path("image.png")
        assert flow_id == ""
        assert file_name == "image.png"

    def test_parse_empty_prefix(self):
        """Test parsing when prefix is empty."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"
        mock_settings.settings.object_storage_bucket_name = "test-bucket"
        mock_settings.settings.object_storage_prefix = ""
        mock_settings.settings.object_storage_tags = {}

        service = S3StorageService(mock_session, mock_settings)

        # Test with no prefix configured
        flow_id, file_name = service.parse_file_path("user_123/image.png")
        assert flow_id == "user_123"
        assert file_name == "image.png"


class TestParseFilePathRoundTrip:
    """Test that parse_file_path correctly reverses build_full_path."""

    def test_local_storage_round_trip(self):
        """Test that parse reverses build for local storage."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        # Build a path
        full_path = service.build_full_path("user_123", "image.png")
        assert full_path == "/data/user_123/image.png"

        # Parse it back
        flow_id, file_name = service.parse_file_path(full_path)
        assert flow_id == "user_123"
        assert file_name == "image.png"

    def test_s3_storage_round_trip(self):
        """Test that parse reverses build for S3 storage."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"
        mock_settings.settings.object_storage_bucket_name = "test-bucket"
        mock_settings.settings.object_storage_prefix = "files/"
        mock_settings.settings.object_storage_tags = {}

        service = S3StorageService(mock_session, mock_settings)

        # Build a path
        full_path = service.build_full_path("user_123", "image.png")
        assert full_path == "files/user_123/image.png"

        # Parse it back
        flow_id, file_name = service.parse_file_path(full_path)
        assert flow_id == "user_123"
        assert file_name == "image.png"

    def test_s3_storage_round_trip_nested(self):
        """Test round trip with nested flow_id."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"
        mock_settings.settings.object_storage_bucket_name = "test-bucket"
        mock_settings.settings.object_storage_prefix = "files-test-1/"
        mock_settings.settings.object_storage_tags = {}

        service = S3StorageService(mock_session, mock_settings)

        # Build a path with nested flow_id
        full_path = service.build_full_path(
            "afffa27a-a9f0-4511-b1a9-7e6cb2b3df05", "2025-12-07_14-47-29_langflow_pid_mem_usage.png"
        )
        assert (
            full_path
            == "files-test-1/afffa27a-a9f0-4511-b1a9-7e6cb2b3df05/2025-12-07_14-47-29_langflow_pid_mem_usage.png"
        )

        # Parse it back
        flow_id, file_name = service.parse_file_path(full_path)
        assert flow_id == "afffa27a-a9f0-4511-b1a9-7e6cb2b3df05"
        assert file_name == "2025-12-07_14-47-29_langflow_pid_mem_usage.png"


class TestWindowsPathHandling:
    """Test that storage services handle Windows-style paths with backslashes."""

    def test_local_storage_windows_path_with_backslashes(self):
        """Test parsing Windows path with backslashes."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "C:\\data"

        service = LocalStorageService(mock_session, mock_settings)

        # Test with Windows path (backslashes)
        flow_id, file_name = service.parse_file_path("user_123\\image.png")
        assert flow_id == "user_123"
        assert file_name == "image.png"

    def test_local_storage_windows_absolute_path(self):
        """Test parsing absolute Windows path."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "C:\\data"

        service = LocalStorageService(mock_session, mock_settings)

        # Test with full Windows path including data_dir
        flow_id, file_name = service.parse_file_path("C:\\data\\user_123\\image.png")
        assert flow_id == "user_123"
        assert file_name == "image.png"

    def test_local_storage_windows_nested_flow_id(self):
        """Test parsing nested Windows path."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "C:\\data"

        service = LocalStorageService(mock_session, mock_settings)

        # Test with nested flow_id using Windows separators
        flow_id, file_name = service.parse_file_path("bucket\\user_123\\image.png")
        assert flow_id == "bucket/user_123"
        assert file_name == "image.png"

    def test_local_storage_windows_mixed_separators(self):
        """Test parsing path with mixed forward slashes and backslashes."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        # Test with mixed separators (can happen on Windows with some file APIs)
        flow_id, file_name = service.parse_file_path("user_123/subfolder\\image.png")
        assert flow_id == "user_123/subfolder"
        assert file_name == "image.png"

    def test_local_storage_windows_temp_path_with_braces(self):
        """Test parsing Windows temp path with curly braces (common pattern)."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "C:\\Users\\test\\AppData\\Local\\Temp"

        service = LocalStorageService(mock_session, mock_settings)

        # Test with actual Windows temp path format that includes curly braces
        test_path = (
            "flow_id\\6d6c70df-fb29-46b2-8bca-56ca9a48c562{2025-12-11_11-56-47_Capt  e tela 2025-12-11 114434.png"
        )
        flow_id, file_name = service.parse_file_path(test_path)
        assert flow_id == "flow_id"
        assert file_name == (
            "6d6c70df-fb29-46b2-8bca-56ca9a48c562{2025-12-11_11-56-47_Capt  e tela 2025-12-11 114434.png"
        )

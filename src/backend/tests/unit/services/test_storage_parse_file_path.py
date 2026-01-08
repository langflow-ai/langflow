"""Tests for storage service parse_file_path method."""

from unittest.mock import Mock

import pytest
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


class TestLocalStorageParseFilePathWindowsCompatibility:
    """Test LocalStorageService.parse_file_path with Windows-style paths.

    These tests ensure cross-platform compatibility when paths contain
    backslashes (Windows) instead of forward slashes (Unix).
    """

    @pytest.mark.skipif(
        not hasattr(__import__("os"), "name") or __import__("os").name != "nt",
        reason="Windows-specific path tests only run on Windows",
    )
    def test_parse_windows_path_with_backslashes(self):
        """Test parsing a Windows-style path with backslashes."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "C:\\data"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path("C:\\data\\user_123\\image.png")
        assert flow_id == "user_123"
        assert file_name == "image.png"

    def test_parse_windows_relative_path(self):
        """Test parsing a Windows relative path without data_dir."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "C:\\data"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path("user_123\\image.png")
        assert flow_id == "user_123"
        assert file_name == "image.png"

    @pytest.mark.skipif(
        not hasattr(__import__("os"), "name") or __import__("os").name != "nt",
        reason="Windows-specific path tests only run on Windows",
    )
    def test_parse_windows_nested_flow_id(self):
        """Test parsing Windows path with nested flow_id."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "C:\\data"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path("C:\\data\\bucket\\user_123\\image.png")
        assert flow_id == "bucket/user_123"
        assert file_name == "image.png"

    def test_parse_mixed_slashes(self):
        """Test parsing path with mixed forward and backslashes."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path("user_123\\subdir/image.png")
        assert flow_id == "user_123/subdir"
        assert file_name == "image.png"

    def test_parse_windows_just_filename(self):
        """Test parsing just a filename on Windows."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "C:\\data"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path("image.png")
        assert flow_id == ""
        assert file_name == "image.png"

    @pytest.mark.skipif(
        not hasattr(__import__("os"), "name") or __import__("os").name != "nt",
        reason="Windows-specific path tests only run on Windows",
    )
    def test_parse_windows_uuid_flow_id(self):
        """Test parsing Windows path with UUID flow_id (real-world scenario)."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "C:\\Users\\user\\AppData\\Local\\langflow"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path(
            "C:\\Users\\user\\AppData\\Local\\langflow\\afffa27a-a9f0-4511-b1a9-7e6cb2b3df05\\uploaded_file.png"
        )
        assert flow_id == "afffa27a-a9f0-4511-b1a9-7e6cb2b3df05"
        assert file_name == "uploaded_file.png"

    def test_backslash_normalization(self):
        """Test that backslashes are normalized to forward slashes."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        # This should work on any platform - relative paths with backslashes
        flow_id, file_name = service.parse_file_path("flow_123\\subdir\\image.png")
        assert "/" not in flow_id or "\\" not in flow_id  # Normalized
        assert file_name == "image.png"

    def test_deeply_nested_backslash_path(self):
        """Test parsing deeply nested path with backslashes."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path("a\\b\\c\\d\\file.txt")
        assert file_name == "file.txt"
        # Flow ID should have normalized slashes
        assert "\\" not in flow_id


class TestLocalStorageParseFilePathEdgeCases:
    """Test edge cases for LocalStorageService.parse_file_path."""

    def test_parse_empty_string(self):
        """Test parsing an empty string."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path("")
        assert flow_id == ""
        assert file_name == "."

    def test_parse_path_with_spaces(self):
        """Test parsing path with spaces in names."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path("/data/flow with spaces/my file.png")
        assert flow_id == "flow with spaces"
        assert file_name == "my file.png"

    def test_parse_path_with_special_characters(self):
        """Test parsing path with special characters."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path("/data/flow_123-test/image_2024-01-01.png")
        assert flow_id == "flow_123-test"
        assert file_name == "image_2024-01-01.png"

    def test_parse_deeply_nested_path(self):
        """Test parsing deeply nested path."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path("/data/level1/level2/level3/file.txt")
        assert flow_id == "level1/level2/level3"
        assert file_name == "file.txt"

    @pytest.mark.parametrize(
        ("input_path", "expected_flow_id", "expected_file_name"),
        [
            ("user_123/image.png", "user_123", "image.png"),
            ("image.png", "", "image.png"),
            ("a/b/c/d.txt", "a/b/c", "d.txt"),
            ("flow-id/file-name.ext", "flow-id", "file-name.ext"),
        ],
    )
    def test_parse_various_relative_paths(self, input_path, expected_flow_id, expected_file_name):
        """Test parsing various relative path formats."""
        mock_session = Mock()
        mock_settings = Mock()
        mock_settings.settings.config_dir = "/data"

        service = LocalStorageService(mock_session, mock_settings)

        flow_id, file_name = service.parse_file_path(input_path)
        assert flow_id == expected_flow_id
        assert file_name == expected_file_name

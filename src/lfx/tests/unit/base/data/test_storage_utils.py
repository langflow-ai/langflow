"""Tests for base/data/storage_utils.py - storage-aware file utilities."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from lfx.base.data.storage_utils import (
    file_exists,
    get_file_size,
    parse_storage_path,
    read_file_bytes,
    read_file_text,
)


class TestParseStoragePath:
    """Test parse_storage_path function."""

    def test_parse_valid_path(self):
        """Test parsing a valid storage path."""
        result = parse_storage_path("flow_123/myfile.txt")
        assert result == ("flow_123", "myfile.txt")

    def test_parse_path_with_subdirs(self):
        """Test parsing path with subdirectories in filename."""
        result = parse_storage_path("flow_123/subdir/myfile.txt")
        assert result == ("flow_123", "subdir/myfile.txt")

    def test_parse_empty_path(self):
        """Test parsing empty path returns None."""
        assert parse_storage_path("") is None
        assert parse_storage_path(None) is None

    def test_parse_path_no_slash(self):
        """Test parsing path without slash returns None."""
        assert parse_storage_path("just_a_filename.txt") is None

    def test_parse_path_empty_parts(self):
        """Test parsing path with empty parts returns None."""
        assert parse_storage_path("/filename.txt") is None
        assert parse_storage_path("flow_id/") is None
        assert parse_storage_path("/") is None

    def test_parse_path_with_multiple_subdirs(self):
        """Test parsing path with multiple subdirectory levels."""
        result = parse_storage_path("flow_456/dir1/dir2/dir3/file.pdf")
        assert result == ("flow_456", "dir1/dir2/dir3/file.pdf")

    def test_parse_path_with_spaces(self):
        """Test parsing path with spaces in filename."""
        result = parse_storage_path("flow_789/my file with spaces.txt")
        assert result == ("flow_789", "my file with spaces.txt")

    def test_parse_path_with_special_chars(self):
        """Test parsing path with special characters."""
        result = parse_storage_path("flow_abc/file-name_v2.0.txt")
        assert result == ("flow_abc", "file-name_v2.0.txt")


@pytest.mark.asyncio
class TestReadFileBytes:
    """Test read_file_bytes function."""

    async def test_read_local_file(self, tmp_path):
        """Test reading a local file when storage_type is local."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = b"Hello, local file!"
        test_file.write_bytes(test_content)

        # Mock settings
        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_bytes(str(test_file))

        assert content == test_content

    async def test_read_local_file_not_found(self):
        """Test reading non-existent local file raises FileNotFoundError."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):  # noqa: SIM117
            with pytest.raises(FileNotFoundError):
                await read_file_bytes("/nonexistent/file.txt")

    async def test_read_s3_file(self):
        """Test reading a file from S3 storage."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()
        expected_content = b"Hello from S3!"
        mock_storage.get_file.return_value = expected_content

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            content = await read_file_bytes("flow_123/test.txt")

        assert content == expected_content
        mock_storage.get_file.assert_called_once_with("flow_123", "test.txt")

    async def test_read_s3_file_invalid_path(self):
        """Test reading S3 file with invalid path format raises ValueError."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):  # noqa: SIM117
            with pytest.raises(ValueError, match="Invalid S3 path format"):
                await read_file_bytes("invalid_path_no_slash")

    async def test_read_s3_file_with_custom_storage_service(self):
        """Test reading S3 file with provided storage service instance."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()
        expected_content = b"Custom storage!"
        mock_storage.get_file.return_value = expected_content

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_bytes("flow_456/custom.txt", storage_service=mock_storage)

        assert content == expected_content
        mock_storage.get_file.assert_called_once_with("flow_456", "custom.txt")

    async def test_s3_mode_with_subdirectories(self):
        """Test S3 mode correctly handles subdirectories in filename."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()
        mock_storage.get_file.return_value = b"Content from subdir"

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            await read_file_bytes("flow_456/subdir1/subdir2/file.txt")

        mock_storage.get_file.assert_called_once_with("flow_456", "subdir1/subdir2/file.txt")


@pytest.mark.asyncio
class TestReadFileText:
    """Test read_file_text function."""

    async def test_read_text_file_default_encoding(self, tmp_path):
        """Test reading text file with default UTF-8 encoding."""
        test_file = tmp_path / "text.txt"
        test_content = "Hello, UTF-8! 你好"
        test_file.write_text(test_content, encoding="utf-8")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_text(str(test_file))

        assert content == test_content

    async def test_read_text_file_custom_encoding(self, tmp_path):
        """Test reading text file with custom encoding."""
        test_file = tmp_path / "latin1.txt"
        test_content = "Hello, Latin-1!"
        test_file.write_text(test_content, encoding="latin-1")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_text(str(test_file), encoding="latin-1")

        assert content == test_content

    async def test_read_text_file_from_s3(self):
        """Test reading text file from S3."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()
        expected_content = "S3 text content"
        mock_storage.get_file.return_value = expected_content.encode("utf-8")

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            content = await read_file_text("flow_789/text.txt")

        assert content == expected_content


class TestGetFileSize:
    """Test get_file_size function."""

    def test_get_local_file_size(self, tmp_path):
        """Test getting size of local file."""
        test_file = tmp_path / "sized.txt"
        test_content = b"X" * 1234
        test_file.write_bytes(test_content)

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            size = get_file_size(str(test_file))

        assert size == 1234

    def test_get_local_file_size_not_found(self):
        """Test getting size of non-existent local file raises FileNotFoundError."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):  # noqa: SIM117
            with pytest.raises(FileNotFoundError):
                get_file_size("/nonexistent/file.txt")

    def test_get_s3_file_size(self):
        """Test getting size of S3 file."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = Mock()

        # Mock async get_file_size to return via asyncio.run
        async def mock_get_size(_flow_id, _filename):
            return 5678

        mock_storage.get_file_size = mock_get_size

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            size = get_file_size("flow_abc/file.bin")

        assert size == 5678

    def test_get_s3_file_size_invalid_path(self):
        """Test getting S3 file size with invalid path raises ValueError."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):  # noqa: SIM117
            with pytest.raises(ValueError, match="Invalid S3 path format"):
                get_file_size("invalid_no_slash")


class TestFileExists:
    """Test file_exists function."""

    def test_file_exists_local_true(self, tmp_path):
        """Test file_exists returns True for existing local file."""
        test_file = tmp_path / "exists.txt"
        test_file.write_bytes(b"content")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            assert file_exists(str(test_file)) is True

    def test_file_exists_local_false(self):
        """Test file_exists returns False for non-existent local file."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            assert file_exists("/nonexistent/file.txt") is False

    def test_file_exists_s3_true(self):
        """Test file_exists returns True for existing S3 file."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = Mock()

        async def mock_get_size(_flow_id, _filename):
            return 100

        mock_storage.get_file_size = mock_get_size

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            assert file_exists("flow_def/exists.txt") is True

    def test_file_exists_s3_false(self):
        """Test file_exists returns False for non-existent S3 file."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = Mock()

        async def mock_get_size(_flow_id, _filename):
            raise FileNotFoundError

        mock_storage.get_file_size = mock_get_size

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            assert file_exists("flow_ghi/nonexistent.txt") is False

    def test_file_exists_invalid_path(self):
        """Test file_exists returns False for invalid S3 path."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            assert file_exists("invalid_no_slash") is False


@pytest.mark.asyncio
class TestStorageUtilsEdgeCases:
    """Test edge cases and special scenarios."""

    async def test_read_binary_content(self, tmp_path):
        """Test reading binary content."""
        test_file = tmp_path / "binary.bin"
        binary_content = bytes(range(256))
        test_file.write_bytes(binary_content)

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_bytes(str(test_file))

        assert content == binary_content

    async def test_read_binary_file_with_null_bytes(self, tmp_path):
        """Test reading binary file with null bytes."""
        test_file = tmp_path / "binary.bin"
        binary_content = b"\x00\x01\x02\xff\xfe\xfd"
        test_file.write_bytes(binary_content)

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_bytes(str(test_file))

        assert content == binary_content

    async def test_read_empty_file(self, tmp_path):
        """Test reading empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_bytes(str(test_file))

        assert content == b""

    async def test_s3_path_with_unicode_filename(self):
        """Test S3 path with unicode characters in filename."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()
        mock_storage.get_file.return_value = b"Content"

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            content = await read_file_bytes("flow_123/文件名.txt")

        assert content == b"Content"
        mock_storage.get_file.assert_called_once_with("flow_123", "文件名.txt")


class TestStorageUtilsSyncEdgeCases:
    """Test sync edge cases and special scenarios."""

    def test_get_size_empty_file(self, tmp_path):
        """Test getting size of empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            size = get_file_size(str(test_file))

        assert size == 0

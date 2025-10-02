"""Unit tests for storage_file_io module."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lfx.utils.storage_file_io import (
    is_remote_path,
    path_exists_async,
    path_exists_sync,
    read_file_async,
    read_file_sync,
    write_file_async,
    write_file_sync,
)


class TestStorageFileIO:
    """Test cases for unified storage file I/O operations."""

    @pytest.fixture
    def mock_storage_service(self):
        """Create a mock storage service."""
        mock_service = MagicMock()
        mock_service.is_remote_path = MagicMock(return_value=False)
        mock_service.parse_path = MagicMock(return_value=("test-flow", "test.txt"))
        mock_service.path_exists = AsyncMock(return_value=True)
        mock_service.read_file = AsyncMock(return_value=b"test content")
        mock_service.write_file = AsyncMock(return_value="/path/to/test.txt")
        return mock_service

    @pytest.fixture
    def mock_s3_storage_service(self):
        """Create a mock S3 storage service."""
        mock_service = MagicMock()
        mock_service.is_remote_path = MagicMock(return_value=True)
        mock_service.parse_path = MagicMock(return_value=("flow-123", "document.pdf"))
        mock_service.path_exists = AsyncMock(return_value=True)
        mock_service.read_file = AsyncMock(return_value=b"S3 file content")
        mock_service.write_file = AsyncMock(return_value="s3://bucket/prefix/flow-123/document.pdf")
        return mock_service

    # Tests for read_file_async
    @pytest.mark.asyncio
    async def test_read_file_async_with_storage_service(self, mock_storage_service):
        """Test reading file with storage service available."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = await read_file_async("/path/to/test.txt")

            assert result == b"test content"
            mock_storage_service.read_file.assert_called_once_with("/path/to/test.txt")

    @pytest.mark.asyncio
    async def test_read_file_async_s3_path(self, mock_s3_storage_service):
        """Test reading S3 file with storage service."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_s3_storage_service):
            result = await read_file_async("s3://bucket/prefix/flow-123/document.pdf")

            assert result == b"S3 file content"
            mock_s3_storage_service.read_file.assert_called_once_with("s3://bucket/prefix/flow-123/document.pdf")

    @pytest.mark.asyncio
    async def test_read_file_async_without_storage_service(self, tmp_path):
        """Test reading file without storage service falls back to direct read."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"fallback content")

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=None):
            result = await read_file_async(str(test_file))

            assert result == b"fallback content"

    @pytest.mark.asyncio
    async def test_read_file_async_file_not_found(self, mock_storage_service):
        """Test reading non-existent file raises FileNotFoundError."""
        mock_storage_service.read_file.side_effect = FileNotFoundError("File not found")

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            with pytest.raises(FileNotFoundError):
                await read_file_async("/path/to/nonexistent.txt")

    # Tests for read_file_sync
    def test_read_file_sync_with_storage_service(self, mock_storage_service):
        """Test synchronous file read with storage service."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = read_file_sync("/path/to/test.txt")

            assert result == b"test content"
            mock_storage_service.read_file.assert_called_once_with("/path/to/test.txt")

    def test_read_file_sync_s3_path(self, mock_s3_storage_service):
        """Test synchronous S3 file read."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_s3_storage_service):
            result = read_file_sync("s3://bucket/prefix/flow-123/document.pdf")

            assert result == b"S3 file content"

    # Tests for write_file_async
    @pytest.mark.asyncio
    async def test_write_file_async_with_storage_service(self, mock_storage_service):
        """Test writing file with storage service."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = await write_file_async("/path/to/test.txt", b"new content")

            assert result == "/path/to/test.txt"
            mock_storage_service.write_file.assert_called_once_with(
                "/path/to/test.txt", b"new content", flow_id=None
            )

    @pytest.mark.asyncio
    async def test_write_file_async_with_flow_id(self, mock_storage_service):
        """Test writing file with explicit flow_id."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = await write_file_async("test.txt", b"content", flow_id="my-flow")

            assert result == "/path/to/test.txt"
            mock_storage_service.write_file.assert_called_once_with("test.txt", b"content", flow_id="my-flow")

    @pytest.mark.asyncio
    async def test_write_file_async_s3_path(self, mock_s3_storage_service):
        """Test writing to S3 with storage service."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_s3_storage_service):
            result = await write_file_async("s3://bucket/prefix/flow-123/new.txt", b"S3 content")

            assert result == "s3://bucket/prefix/flow-123/document.pdf"
            mock_s3_storage_service.write_file.assert_called_once_with(
                "s3://bucket/prefix/flow-123/new.txt", b"S3 content", flow_id=None
            )

    @pytest.mark.asyncio
    async def test_write_file_async_without_storage_service(self, tmp_path):
        """Test writing file without storage service falls back to direct write."""
        test_file = tmp_path / "test.txt"

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=None):
            result = await write_file_async(str(test_file), b"fallback content")

            assert result == str(test_file)
            assert test_file.read_bytes() == b"fallback content"

    # Tests for write_file_sync
    def test_write_file_sync_with_storage_service(self, mock_storage_service):
        """Test synchronous file write with storage service."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = write_file_sync("/path/to/test.txt", b"sync content")

            assert result == "/path/to/test.txt"
            mock_storage_service.write_file.assert_called_once_with(
                "/path/to/test.txt", b"sync content", flow_id=None
            )

    def test_write_file_sync_s3_path(self, mock_s3_storage_service):
        """Test synchronous S3 file write."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_s3_storage_service):
            result = write_file_sync("s3://bucket/prefix/flow-123/sync.txt", b"S3 sync content")

            assert result == "s3://bucket/prefix/flow-123/document.pdf"

    # Tests for path_exists_async
    @pytest.mark.asyncio
    async def test_path_exists_async_true(self, mock_storage_service):
        """Test checking if path exists returns True."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = await path_exists_async("/path/to/test.txt")

            assert result is True
            mock_storage_service.parse_path.assert_called_once_with("/path/to/test.txt")
            mock_storage_service.path_exists.assert_called_once_with("test-flow", "test.txt")

    @pytest.mark.asyncio
    async def test_path_exists_async_false(self, mock_storage_service):
        """Test checking if path exists returns False."""
        mock_storage_service.path_exists.return_value = False

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = await path_exists_async("/path/to/nonexistent.txt")

            assert result is False

    @pytest.mark.asyncio
    async def test_path_exists_async_invalid_path(self, mock_storage_service):
        """Test path exists with invalid path returns False."""
        mock_storage_service.parse_path.return_value = None

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = await path_exists_async("invalid://path")

            assert result is False

    @pytest.mark.asyncio
    async def test_path_exists_async_without_storage_service(self, tmp_path):
        """Test path exists without storage service falls back to Path.exists()."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=None):
            result = await path_exists_async(str(test_file))
            assert result is True

            result = await path_exists_async(str(tmp_path / "nonexistent.txt"))
            assert result is False

    # Tests for path_exists_sync
    def test_path_exists_sync_true(self, mock_storage_service):
        """Test synchronous path exists check returns True."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = path_exists_sync("/path/to/test.txt")

            assert result is True

    def test_path_exists_sync_false(self, mock_storage_service):
        """Test synchronous path exists check returns False."""
        mock_storage_service.path_exists.return_value = False

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = path_exists_sync("/path/to/nonexistent.txt")

            assert result is False

    # Tests for is_remote_path
    def test_is_remote_path_true(self, mock_s3_storage_service):
        """Test detecting remote path (S3 URI) returns True."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_s3_storage_service):
            result = is_remote_path("s3://bucket/prefix/flow/file.txt")

            assert result is True
            mock_s3_storage_service.is_remote_path.assert_called_once_with("s3://bucket/prefix/flow/file.txt")

    def test_is_remote_path_false(self, mock_storage_service):
        """Test detecting local path returns False."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = is_remote_path("/local/path/file.txt")

            assert result is False
            mock_storage_service.is_remote_path.assert_called_once_with("/local/path/file.txt")

    def test_is_remote_path_without_storage_service(self):
        """Test is_remote_path without storage service returns False."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=None):
            result = is_remote_path("s3://bucket/file.txt")

            assert result is False

    # Edge case tests
    @pytest.mark.asyncio
    async def test_read_file_async_empty_file(self, mock_storage_service):
        """Test reading empty file."""
        mock_storage_service.read_file.return_value = b""

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = await read_file_async("/path/to/empty.txt")

            assert result == b""

    @pytest.mark.asyncio
    async def test_write_file_async_empty_content(self, mock_storage_service):
        """Test writing empty content."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = await write_file_async("/path/to/empty.txt", b"")

            mock_storage_service.write_file.assert_called_once_with("/path/to/empty.txt", b"", flow_id=None)

    @pytest.mark.asyncio
    async def test_path_exists_async_error_handling(self, mock_storage_service):
        """Test path exists handles exceptions gracefully."""
        mock_storage_service.path_exists.side_effect = Exception("Storage error")

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_storage_service):
            result = await path_exists_async("/path/to/test.txt")

            # Should return False on error
            assert result is False

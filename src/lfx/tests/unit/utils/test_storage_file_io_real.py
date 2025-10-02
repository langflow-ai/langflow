"""Integration tests for storage_file_io module with real storage services.

These tests use actual LocalStorageService instances with real file I/O
to ensure the storage_file_io layer works correctly end-to-end.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lfx.services.storage.local import LocalStorageService
from lfx.utils.storage_file_io import (
    is_remote_path,
    path_exists_async,
    path_exists_sync,
    read_file_async,
    read_file_sync,
    write_file_async,
    write_file_sync,
)


class TestStorageFileIOWithRealStorage:
    """Test storage_file_io with real LocalStorageService (not mocked)."""

    @pytest.fixture
    def real_storage_service(self, tmp_path):
        """Create a real LocalStorageService instance."""
        return LocalStorageService(data_dir=tmp_path)

    @pytest.fixture
    def test_content(self):
        """Test file content."""
        return b"This is real test content from storage_file_io tests!"

    # Tests for read_file_async with real storage
    @pytest.mark.asyncio
    async def test_read_file_async_local_path(self, real_storage_service, test_content, tmp_path):
        """Test reading local file through storage_file_io with real storage."""
        # Create a real file
        await real_storage_service.save_file("test-flow", "document.txt", test_content)
        file_path = real_storage_service.build_full_path("test-flow", "document.txt")

        # Read through storage_file_io
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            result = await read_file_async(file_path)

        assert result == test_content

    @pytest.mark.asyncio
    async def test_read_file_async_relative_path(self, real_storage_service, test_content):
        """Test reading with relative path defaults to 'local' flow."""
        # Create file in 'local' flow
        await real_storage_service.save_file("local", "test.txt", test_content)

        # Read with just filename
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            result = await read_file_async("test.txt")

        assert result == test_content

    @pytest.mark.asyncio
    async def test_read_file_async_without_storage_service(self, tmp_path, test_content):
        """Test fallback to direct file read when no storage service."""
        # Create a file directly
        test_file = tmp_path / "fallback.txt"
        test_file.write_bytes(test_content)

        # Read without storage service
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=None):
            result = await read_file_async(str(test_file))

        assert result == test_content

    @pytest.mark.asyncio
    async def test_read_file_async_file_not_found(self, real_storage_service):
        """Test FileNotFoundError is raised for non-existent file."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            with pytest.raises(FileNotFoundError):
                await read_file_async("/nonexistent/path/file.txt")

    # Tests for read_file_sync with real storage
    def test_read_file_sync_local_path(self, real_storage_service, test_content, tmp_path):
        """Test synchronous read with real storage."""
        # Create a real file
        import asyncio

        asyncio.run(real_storage_service.save_file("sync-flow", "sync.txt", test_content))
        file_path = real_storage_service.build_full_path("sync-flow", "sync.txt")

        # Read synchronously
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            result = read_file_sync(file_path)

        assert result == test_content

    # Tests for write_file_async with real storage
    @pytest.mark.asyncio
    async def test_write_file_async_creates_file(self, real_storage_service, test_content):
        """Test writing file actually creates it on disk."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            result_path = await write_file_async("new.txt", test_content, flow_id="write-flow")

        # Verify file was actually created
        assert Path(result_path).exists()
        content = await real_storage_service.get_file("write-flow", "new.txt")
        assert content == test_content

    @pytest.mark.asyncio
    async def test_write_file_async_full_path(self, real_storage_service, test_content):
        """Test writing with full path."""
        file_path = real_storage_service.build_full_path("full-flow", "full.txt")

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            result_path = await write_file_async(file_path, test_content)

        assert result_path == file_path
        assert Path(result_path).exists()

    @pytest.mark.asyncio
    async def test_write_file_async_without_storage_service(self, tmp_path, test_content):
        """Test fallback to direct write when no storage service."""
        test_file = tmp_path / "direct.txt"

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=None):
            result = await write_file_async(str(test_file), test_content)

        assert result == str(test_file)
        assert test_file.exists()
        assert test_file.read_bytes() == test_content

    # Tests for write_file_sync with real storage
    def test_write_file_sync_creates_file(self, real_storage_service, test_content):
        """Test synchronous write actually creates file."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            result_path = write_file_sync("sync_write.txt", test_content, flow_id="sync-flow")

        # Verify file exists
        assert Path(result_path).exists()

    # Tests for path_exists_async with real storage
    @pytest.mark.asyncio
    async def test_path_exists_async_true(self, real_storage_service, test_content):
        """Test path_exists returns True for existing file."""
        # Create real file
        await real_storage_service.save_file("exists-flow", "exists.txt", test_content)
        file_path = real_storage_service.build_full_path("exists-flow", "exists.txt")

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            result = await path_exists_async(file_path)

        assert result is True

    @pytest.mark.asyncio
    async def test_path_exists_async_false(self, real_storage_service):
        """Test path_exists returns False for non-existent file."""
        file_path = real_storage_service.build_full_path("noflow", "nofile.txt")

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            result = await path_exists_async(file_path)

        assert result is False

    @pytest.mark.asyncio
    async def test_path_exists_async_without_storage_service(self, tmp_path, test_content):
        """Test fallback path existence check."""
        test_file = tmp_path / "exists_check.txt"
        test_file.write_bytes(test_content)

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=None):
            result = await path_exists_async(str(test_file))

        assert result is True

    # Tests for path_exists_sync with real storage
    def test_path_exists_sync_true(self, real_storage_service, test_content):
        """Test synchronous path exists check."""
        import asyncio

        asyncio.run(real_storage_service.save_file("sync-exists", "file.txt", test_content))
        file_path = real_storage_service.build_full_path("sync-exists", "file.txt")

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            result = path_exists_sync(file_path)

        assert result is True

    # Tests for is_remote_path with real storage
    def test_is_remote_path_local_storage(self, real_storage_service):
        """Test is_remote_path with real LocalStorageService."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            # Local storage should always return False
            assert is_remote_path("s3://bucket/file.txt") is False
            assert is_remote_path("/local/path.txt") is False

    def test_is_remote_path_without_storage_service(self):
        """Test is_remote_path without storage service."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=None):
            # No storage service defaults to False
            assert is_remote_path("s3://bucket/file.txt") is False

    # Integration tests - complete workflows
    @pytest.mark.asyncio
    async def test_complete_workflow_write_check_read(self, real_storage_service, test_content):
        """Test complete workflow: write → check exists → read."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            # Write file
            write_path = await write_file_async("workflow.txt", test_content, flow_id="workflow")

            # Check it exists
            exists = await path_exists_async(write_path)
            assert exists is True

            # Read it back
            read_content = await read_file_async(write_path)
            assert read_content == test_content

    @pytest.mark.asyncio
    async def test_overwrite_existing_file(self, real_storage_service):
        """Test writing over existing file works correctly."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            # Write initial content
            path = await write_file_async("overwrite.txt", b"initial", flow_id="test")

            # Overwrite
            await write_file_async("overwrite.txt", b"updated", flow_id="test")

            # Read and verify
            content = await read_file_async(path)
            assert content == b"updated"

    @pytest.mark.asyncio
    async def test_multiple_flows_isolation(self, real_storage_service, test_content):
        """Test that different flows are properly isolated."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            # Write same filename to different flows
            path1 = await write_file_async("same.txt", b"flow1 content", flow_id="flow-1")
            path2 = await write_file_async("same.txt", b"flow2 content", flow_id="flow-2")

            # Verify they're different files
            assert path1 != path2

            # Verify each has correct content
            content1 = await read_file_async(path1)
            content2 = await read_file_async(path2)

            assert content1 == b"flow1 content"
            assert content2 == b"flow2 content"

    @pytest.mark.asyncio
    async def test_empty_file_handling(self, real_storage_service):
        """Test that empty files are handled correctly."""
        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            # Write empty file
            path = await write_file_async("empty.txt", b"", flow_id="empty-test")

            # Verify it exists
            exists = await path_exists_async(path)
            assert exists is True

            # Read it back
            content = await read_file_async(path)
            assert content == b""

    def test_sync_wrapper_consistency(self, real_storage_service, test_content):
        """Test that sync wrappers produce same results as async versions."""
        import asyncio

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=real_storage_service):
            # Write using sync
            sync_path = write_file_sync("sync_test.txt", test_content, flow_id="consistency")

            # Read using sync
            sync_content = read_file_sync(sync_path)

            # Verify using async
            async_content = asyncio.run(read_file_async(sync_path))

            assert sync_content == async_content == test_content

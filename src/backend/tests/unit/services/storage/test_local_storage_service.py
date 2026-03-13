"""Tests for LocalStorageService."""

from unittest.mock import Mock

import anyio
import pytest
from langflow.services.storage.local import LocalStorageService


@pytest.fixture
def mock_settings_service():
    """Create a mock settings service."""
    settings_service = Mock()
    settings_service.settings.config_dir = "/tmp/langflow_test"  # noqa: S108
    return settings_service


@pytest.fixture
def mock_session_service():
    """Create a mock session service."""
    return Mock()


@pytest.fixture
async def local_storage_service(mock_session_service, mock_settings_service, tmp_path):
    """Create a LocalStorageService instance for testing."""
    # Override the config dir to use tmp_path
    mock_settings_service.settings.config_dir = str(tmp_path)
    service = LocalStorageService(mock_session_service, mock_settings_service)
    yield service
    # Cleanup
    await service.teardown()


@pytest.mark.asyncio
class TestLocalStorageServiceBasics:
    """Test basic LocalStorageService functionality."""

    async def test_initialization(self, local_storage_service):
        """Test that the service initializes correctly."""
        assert local_storage_service.ready is True
        assert local_storage_service.data_dir is not None

    async def test_build_full_path(self, local_storage_service):
        """Test building full path for a file."""
        flow_id = "test_flow_123"
        file_name = "test_file.txt"

        full_path = local_storage_service.build_full_path(flow_id, file_name)

        assert flow_id in full_path
        assert file_name in full_path
        assert full_path.endswith("test_file.txt")

    async def test_resolve_component_path(self, local_storage_service):
        """Test resolving logical path to filesystem path."""
        logical_path = "flow_123/myfile.txt"

        resolved = local_storage_service.resolve_component_path(logical_path)

        assert "flow_123" in resolved
        assert "myfile.txt" in resolved
        assert resolved.startswith(str(local_storage_service.data_dir))

    async def test_resolve_component_path_malformed(self, local_storage_service):
        """Test resolving malformed logical path returns it as-is."""
        malformed_path = "just_a_filename.txt"

        resolved = local_storage_service.resolve_component_path(malformed_path)

        assert resolved == malformed_path


@pytest.mark.asyncio
class TestLocalStorageServiceFileOperations:
    """Test file operations in LocalStorageService."""

    async def test_save_and_get_file(self, local_storage_service):
        """Test saving and retrieving a file."""
        flow_id = "test_flow"
        file_name = "test.txt"
        data = b"Hello, World!"

        # Save file
        await local_storage_service.save_file(flow_id, file_name, data)

        # Retrieve file
        retrieved_data = await local_storage_service.get_file(flow_id, file_name)

        assert retrieved_data == data

    async def test_save_file_creates_directory(self, local_storage_service):
        """Test that save_file creates the flow directory if it doesn't exist."""
        flow_id = "new_flow_dir"
        file_name = "test.txt"
        data = b"test content"

        # Ensure directory doesn't exist
        flow_dir = local_storage_service.data_dir / flow_id
        assert not await flow_dir.exists()

        # Save file
        await local_storage_service.save_file(flow_id, file_name, data)

        # Directory should now exist
        assert await flow_dir.exists()
        assert await flow_dir.is_dir()

    async def test_save_file_overwrites_existing(self, local_storage_service):
        """Test that saving a file with the same name overwrites the existing file."""
        flow_id = "test_flow"
        file_name = "overwrite.txt"

        # Save initial file
        await local_storage_service.save_file(flow_id, file_name, b"original")

        # Overwrite with new data
        new_data = b"updated content"
        await local_storage_service.save_file(flow_id, file_name, new_data)

        # Verify new data
        retrieved = await local_storage_service.get_file(flow_id, file_name)
        assert retrieved == new_data

    async def test_get_file_not_found(self, local_storage_service):
        """Test getting a file that doesn't exist raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            await local_storage_service.get_file("nonexistent_flow", "nonexistent.txt")

        assert "not found" in str(exc_info.value).lower()

    async def test_save_binary_file(self, local_storage_service):
        """Test saving and retrieving binary data."""
        flow_id = "binary_flow"
        file_name = "binary.bin"
        # Create some binary data
        data = bytes(range(256))

        await local_storage_service.save_file(flow_id, file_name, data)
        retrieved = await local_storage_service.get_file(flow_id, file_name)

        assert retrieved == data


@pytest.mark.asyncio
class TestLocalStorageServiceListOperations:
    """Test list operations in LocalStorageService."""

    async def test_list_files_empty_directory(self, local_storage_service):
        """Test listing files in an empty/nonexistent directory returns empty list."""
        # New implementation returns empty list instead of raising FileNotFoundError
        listed_files = await local_storage_service.list_files("nonexistent_flow")
        assert listed_files == []

    async def test_list_files_with_files(self, local_storage_service):
        """Test listing files in a directory with files."""
        flow_id = "list_test_flow"
        files = ["file1.txt", "file2.txt", "file3.csv"]

        # Create files
        for file_name in files:
            await local_storage_service.save_file(flow_id, file_name, b"content")

        # List files
        listed_files = await local_storage_service.list_files(flow_id)

        assert len(listed_files) == 3
        assert set(listed_files) == set(files)

    async def test_list_files_with_numeric_flow_id(self, local_storage_service):
        """Test listing files with numeric flow_id (converted to string)."""
        flow_id = 12345
        file_name = "test.txt"

        await local_storage_service.save_file(str(flow_id), file_name, b"content")

        # List with numeric flow_id
        listed_files = await local_storage_service.list_files(flow_id)

        assert file_name in listed_files

    async def test_list_files_async_iteration(self, local_storage_service):
        """Test that list_files uses async iteration correctly (folder_path.iterdir())."""
        flow_id = "async_iter_test"
        files = ["file1.txt", "file2.txt", "file3.txt"]

        # Create files
        for file_name in files:
            await local_storage_service.save_file(flow_id, file_name, b"content")

        # List files - this tests the async for loop with folder_path.iterdir()
        listed_files = await local_storage_service.list_files(flow_id)

        # Verify all files are listed (tests async iteration works)
        assert len(listed_files) == 3
        assert set(listed_files) == set(files)

    async def test_list_files_excludes_directories(self, local_storage_service):
        """Test that list_files only returns files, not directories."""
        flow_id = "dir_test"
        file_name = "test.txt"

        # Create a file
        await local_storage_service.save_file(flow_id, file_name, b"content")

        # Create a subdirectory (by creating a file in a subdirectory)
        await local_storage_service.save_file(f"{flow_id}/subdir", "nested.txt", b"content")

        # List files - should only return files in the flow_id directory, not subdirectories
        listed_files = await local_storage_service.list_files(flow_id)

        # Should only return the file in the root, not the nested one
        assert file_name in listed_files
        assert "nested.txt" not in listed_files  # Nested file is in subdirectory


@pytest.mark.asyncio
class TestLocalStorageServiceDeleteOperations:
    """Test delete operations in LocalStorageService."""

    async def test_delete_existing_file(self, local_storage_service):
        """Test deleting an existing file."""
        flow_id = "delete_flow"
        file_name = "to_delete.txt"

        # Create file
        await local_storage_service.save_file(flow_id, file_name, b"delete me")

        # Verify it exists
        files = await local_storage_service.list_files(flow_id)
        assert file_name in files

        # Delete file
        await local_storage_service.delete_file(flow_id, file_name)

        # Verify it's gone
        with pytest.raises(FileNotFoundError):
            await local_storage_service.get_file(flow_id, file_name)

    async def test_delete_nonexistent_file(self, local_storage_service):
        """Test deleting a non-existent file doesn't raise an error."""
        flow_id = "delete_flow"

        # Create the flow directory first
        await local_storage_service.save_file(flow_id, "dummy.txt", b"dummy")

        # Delete non-existent file should not raise
        await local_storage_service.delete_file(flow_id, "nonexistent.txt")

    async def test_delete_multiple_files(self, local_storage_service):
        """Test deleting multiple files from the same flow."""
        flow_id = "multi_delete_flow"
        files = ["file1.txt", "file2.txt", "file3.txt"]

        # Create files
        for file_name in files:
            await local_storage_service.save_file(flow_id, file_name, b"content")

        # Delete all files
        for file_name in files:
            await local_storage_service.delete_file(flow_id, file_name)

        # Verify all are gone
        listed_files = await local_storage_service.list_files(flow_id)
        assert len(listed_files) == 0


@pytest.mark.asyncio
class TestLocalStorageServiceFileSizeOperations:
    """Test file size operations in LocalStorageService."""

    async def test_get_file_size(self, local_storage_service):
        """Test getting the size of a file."""
        flow_id = "size_flow"
        file_name = "sized.txt"
        data = b"A" * 100  # 100 bytes

        await local_storage_service.save_file(flow_id, file_name, data)

        size = await local_storage_service.get_file_size(flow_id, file_name)

        assert size == 100

    async def test_get_file_size_empty_file(self, local_storage_service):
        """Test getting the size of an empty file."""
        flow_id = "size_flow"
        file_name = "empty.txt"

        await local_storage_service.save_file(flow_id, file_name, b"")

        size = await local_storage_service.get_file_size(flow_id, file_name)

        assert size == 0

    async def test_get_file_size_nonexistent(self, local_storage_service):
        """Test getting size of non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await local_storage_service.get_file_size("no_flow", "no_file.txt")

    async def test_get_file_size_large_file(self, local_storage_service):
        """Test getting the size of a large file."""
        flow_id = "size_flow"
        file_name = "large.bin"
        data = b"X" * (1024 * 1024)  # 1 MB

        await local_storage_service.save_file(flow_id, file_name, data)

        size = await local_storage_service.get_file_size(flow_id, file_name)

        assert size == 1024 * 1024


@pytest.mark.asyncio
class TestLocalStorageServiceTeardown:
    """Test teardown operations in LocalStorageService."""

    async def test_teardown(self, local_storage_service):
        """Test that teardown completes without errors."""
        await local_storage_service.teardown()
        # Local storage teardown is a no-op, so just verify it doesn't raise


@pytest.mark.asyncio
class TestLocalStorageServiceEdgeCases:
    """Test edge cases and error conditions."""

    async def test_save_file_with_special_characters(self, local_storage_service):
        """Test saving files with special characters in names."""
        flow_id = "special_chars_flow"
        file_name = "test-file_2024.txt"
        data = b"special content"

        await local_storage_service.save_file(flow_id, file_name, data)
        retrieved = await local_storage_service.get_file(flow_id, file_name)

        assert retrieved == data

    async def test_save_file_with_unicode_content(self, local_storage_service):
        """Test saving files with unicode content."""
        flow_id = "unicode_flow"
        file_name = "unicode.txt"
        data = "Hello 世界 🌍".encode()

        await local_storage_service.save_file(flow_id, file_name, data)
        retrieved = await local_storage_service.get_file(flow_id, file_name)

        assert retrieved == data
        assert retrieved.decode("utf-8") == "Hello 世界 🌍"

    async def test_concurrent_file_operations(self, local_storage_service):
        """Test concurrent file operations on different files."""
        flow_id = "concurrent_flow"
        files = [f"file_{i}.txt" for i in range(10)]

        # Save files concurrently
        async with anyio.create_task_group() as tg:
            for i, file_name in enumerate(files):
                data = f"content_{i}".encode()
                tg.start_soon(local_storage_service.save_file, flow_id, file_name, data)

        # Verify all files were saved
        listed = await local_storage_service.list_files(flow_id)
        assert len(listed) == 10

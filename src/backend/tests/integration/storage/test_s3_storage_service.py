"""Integration tests for S3StorageService using real AWS S3.

These tests use actual AWS credentials and interact with a real S3 bucket.
They are designed to be safe and clean up after themselves.

AWS credentials must be set as environment variables:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_DEFAULT_REGION (optional, defaults to us-west-2)
"""

import contextlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from langflow.services.storage.s3 import S3StorageService

# Mark all tests in this module as requiring API keys
pytestmark = pytest.mark.api_key_required


@pytest.fixture
def aws_credentials():
    """Verify AWS credentials are set via environment variables."""
    required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]

    if missing_vars:
        pytest.skip(f"Missing required environment variables: {', '.join(missing_vars)}")

    # Set default region if not provided
    if not os.environ.get("AWS_DEFAULT_REGION"):
        os.environ["AWS_DEFAULT_REGION"] = "us-west-2"

    # No cleanup needed - we're using existing env vars


@pytest.fixture
def mock_settings_service():
    """Create a mock settings service with S3 configuration.

    Configuration via environment variables:
    - LANGFLOW_OBJECT_STORAGE_BUCKET_NAME: S3 bucket name (default: langflow-ci)
    - LANGFLOW_OBJECT_STORAGE_PREFIX: S3 prefix (default: test-files-1)
    - LANGFLOW_OBJECT_STORAGE_TAGS: S3 tags as JSON string (default: {"env": "test-1"})

    Note: All settings use LANGFLOW_OBJECT_STORAGE_* names to test that
    the S3StorageService properly respects these settings.
    """
    settings_service = Mock()
    settings_service.settings.config_dir = str(Path(tempfile.gettempdir()) / "langflow_test")

    # Bucket name from env or default
    settings_service.settings.object_storage_bucket_name = os.environ.get(
        "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME", "langflow-ci"
    )

    # Prefix from env - using standard LANGFLOW env var name
    settings_service.settings.object_storage_prefix = os.environ.get("LANGFLOW_OBJECT_STORAGE_PREFIX", "test-files-1")

    # Tags from env - using standard LANGFLOW env var name
    default_tags = {"env": "test-1"}
    tags_str = os.environ.get("LANGFLOW_OBJECT_STORAGE_TAGS")
    if tags_str:
        try:
            settings_service.settings.object_storage_tags = json.loads(tags_str)
        except json.JSONDecodeError:
            settings_service.settings.object_storage_tags = default_tags
    else:
        settings_service.settings.object_storage_tags = default_tags

    return settings_service


@pytest.fixture
def mock_session_service():
    """Create a mock session service."""
    return Mock()


@pytest.fixture
async def s3_storage_service(mock_session_service, mock_settings_service, _aws_credentials):
    """Create an S3StorageService instance for testing with real AWS."""
    service = S3StorageService(mock_session_service, mock_settings_service)
    yield service
    await service.teardown()


@pytest.fixture
def test_flow_id():
    """Unique flow ID for testing to avoid conflicts."""
    import uuid

    return f"test_flow_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
class TestS3StorageServiceInitialization:
    """Test S3StorageService initialization."""

    async def test_initialization(self, s3_storage_service):
        """Test that the service initializes correctly and respects settings."""
        assert s3_storage_service.ready is True

        # Verify bucket name matches env or default
        expected_bucket = os.environ.get("LANGFLOW_OBJECT_STORAGE_BUCKET_NAME", "langflow-ci")
        assert s3_storage_service.bucket_name == expected_bucket

        # Verify prefix matches env or default (with trailing slash)
        # This tests that S3StorageService respects LANGFLOW_OBJECT_STORAGE_PREFIX
        expected_prefix = os.environ.get("LANGFLOW_OBJECT_STORAGE_PREFIX", "test-files-1")
        assert s3_storage_service.prefix == f"{expected_prefix}/"

        # Verify tags match env or default
        # This tests that S3StorageService respects LANGFLOW_OBJECT_STORAGE_TAGS
        default_tags = {"env": "test-1"}
        tags_str = os.environ.get("LANGFLOW_OBJECT_STORAGE_TAGS")
        expected_tags = json.loads(tags_str) if tags_str else default_tags
        assert s3_storage_service.tags == expected_tags

    async def test_build_full_path(self, s3_storage_service):
        """Test building full S3 key with configured prefix."""
        expected_prefix = os.environ.get("LANGFLOW_OBJECT_STORAGE_PREFIX", "test-files-1")
        key = s3_storage_service.build_full_path("flow_123", "test.txt")
        assert key == f"{expected_prefix}/flow_123/test.txt"

    async def test_resolve_component_path(self, s3_storage_service):
        """Test that resolve_component_path returns logical path as-is."""
        logical_path = "flow_123/myfile.txt"
        resolved = s3_storage_service.resolve_component_path(logical_path)
        assert resolved == logical_path


@pytest.mark.asyncio
class TestS3StorageServiceFileOperations:
    """Test file operations in S3StorageService with real S3."""

    async def test_save_and_get_file(self, s3_storage_service, test_flow_id):
        """Test saving and retrieving a file."""
        file_name = "test.txt"
        data = b"Hello, S3!"

        try:
            # Save file
            await s3_storage_service.save_file(test_flow_id, file_name, data)

            # Retrieve file
            retrieved = await s3_storage_service.get_file(test_flow_id, file_name)

            assert retrieved == data
        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)

    async def test_save_file_overwrites_existing(self, s3_storage_service, test_flow_id):
        """Test that saving a file overwrites existing content."""
        file_name = "overwrite.txt"

        try:
            # Save initial file
            await s3_storage_service.save_file(test_flow_id, file_name, b"original")

            # Overwrite with new data
            new_data = b"updated content"
            await s3_storage_service.save_file(test_flow_id, file_name, new_data)

            # Verify new data
            retrieved = await s3_storage_service.get_file(test_flow_id, file_name)
            assert retrieved == new_data
        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_not_found(self, s3_storage_service, test_flow_id):
        """Test getting a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            await s3_storage_service.get_file(test_flow_id, "nonexistent.txt")

    async def test_save_binary_file(self, s3_storage_service, test_flow_id):
        """Test saving and retrieving binary data."""
        file_name = "binary.bin"
        data = bytes(range(256))

        try:
            await s3_storage_service.save_file(test_flow_id, file_name, data)
            retrieved = await s3_storage_service.get_file(test_flow_id, file_name)

            assert retrieved == data
        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)

    async def test_save_large_file(self, s3_storage_service, test_flow_id):
        """Test saving and retrieving a larger file (1MB)."""
        file_name = "large.bin"
        data = b"X" * (1024 * 1024)  # 1 MB

        try:
            await s3_storage_service.save_file(test_flow_id, file_name, data)

            # Verify size
            size = await s3_storage_service.get_file_size(test_flow_id, file_name)
            assert size == 1024 * 1024

            # Verify content
            retrieved = await s3_storage_service.get_file(test_flow_id, file_name)
            assert retrieved == data
        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)


@pytest.mark.asyncio
class TestS3StorageServiceStreamOperations:
    """Test streaming operations in S3StorageService."""

    async def test_get_file_stream(self, s3_storage_service, test_flow_id):
        """Test streaming a file from S3."""
        file_name = "stream.txt"
        data = b"A" * 10000  # 10KB

        try:
            await s3_storage_service.save_file(test_flow_id, file_name, data)

            # Stream the file
            chunks = [
                chunk async for chunk in s3_storage_service.get_file_stream(test_flow_id, file_name, chunk_size=1024)
            ]

            # Verify content
            streamed_data = b"".join(chunks)
            assert streamed_data == data
            assert len(chunks) > 1  # Should be multiple chunks
        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_stream_not_found(self, s3_storage_service, test_flow_id):
        """Test streaming a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            async for _ in s3_storage_service.get_file_stream(test_flow_id, "no_file.txt"):
                pass

    async def test_get_file_stream_context_manager_lifecycle(self, s3_storage_service, test_flow_id):
        """Test that context manager stays open during streaming and cleans up properly.

        This test verifies that the async context manager in get_file_stream()
        remains open throughout the entire generator lifecycle, even when yielding
        chunks. The context should only exit after the generator is exhausted or closed.
        """
        file_name = "context_test.txt"
        # Create a file large enough to require multiple chunks
        data = b"B" * 20000  # 20KB, will be multiple chunks with default chunk_size

        try:
            await s3_storage_service.save_file(test_flow_id, file_name, data)

            # Test 1: Verify we can stream all chunks (context stays open)
            chunks = [
                chunk async for chunk in s3_storage_service.get_file_stream(test_flow_id, file_name, chunk_size=1024)
            ]
            # Context manager should still be open at this point
            # If it closed early, we wouldn't be able to get subsequent chunks

            # Verify we got all chunks
            streamed_data = b"".join(chunks)
            assert streamed_data == data
            assert len(chunks) > 1, "Should have multiple chunks to test context lifecycle"

        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_stream_early_termination(self, s3_storage_service, test_flow_id):
        """Test that early termination (client disconnect) properly cleans up resources.

        This test verifies that when a generator is closed early (simulating a client
        disconnect), the context manager properly exits and resources are cleaned up.
        """
        file_name = "early_termination_test.txt"
        data = b"C" * 30000  # 30KB, ensures multiple chunks

        try:
            await s3_storage_service.save_file(test_flow_id, file_name, data)

            # Create generator
            gen = s3_storage_service.get_file_stream(test_flow_id, file_name, chunk_size=1024)

            # Consume only first few chunks (simulating client disconnect)
            chunks_received = []
            chunk_count = 0
            try:
                async for chunk in gen:
                    chunks_received.append(chunk)
                    chunk_count += 1
                    if chunk_count >= 3:  # Only consume first 3 chunks
                        # Close generator early (simulating client disconnect)
                        await gen.aclose()
                        break
            finally:
                # Ensure generator is closed even if break doesn't trigger aclose
                with contextlib.suppress(StopAsyncIteration, RuntimeError):
                    await gen.aclose()

            # Verify we got partial data
            assert len(chunks_received) == 3, "Should have received exactly 3 chunks before termination"
            partial_data = b"".join(chunks_received)
            assert len(partial_data) < len(data), "Should have less data than full file"

            # Verify we can create a new generator and stream the full file
            # (This confirms the previous generator cleaned up properly)
            full_chunks = [
                chunk async for chunk in s3_storage_service.get_file_stream(test_flow_id, file_name, chunk_size=1024)
            ]

            full_data = b"".join(full_chunks)
            assert full_data == data, "Should be able to stream full file after early termination"

        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_stream_multiple_concurrent_streams(self, s3_storage_service, test_flow_id):
        """Test that multiple concurrent streams work correctly with independent context managers.

        This test verifies that each generator has its own context manager lifecycle
        and they don't interfere with each other.
        """
        import asyncio

        file_name = "concurrent_test.txt"
        data = b"D" * 15000  # 15KB

        try:
            await s3_storage_service.save_file(test_flow_id, file_name, data)

            # Create multiple generators concurrently
            gen1 = s3_storage_service.get_file_stream(test_flow_id, file_name, chunk_size=1024)
            gen2 = s3_storage_service.get_file_stream(test_flow_id, file_name, chunk_size=1024)

            # Consume from both generators concurrently using asyncio.gather
            async def consume_gen(gen, chunks_list):
                async for chunk in gen:
                    chunks_list.append(chunk)

            chunks1 = []
            chunks2 = []
            await asyncio.gather(consume_gen(gen1, chunks1), consume_gen(gen2, chunks2))

            # Verify both streams got complete data
            data1 = b"".join(chunks1)
            data2 = b"".join(chunks2)
            assert data1 == data, "First stream should have complete data"
            assert data2 == data, "Second stream should have complete data"

        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)


@pytest.mark.asyncio
class TestS3StorageServiceListOperations:
    """Test list operations in S3StorageService."""

    async def test_list_files_empty(self, s3_storage_service, test_flow_id):
        """Test listing files in an empty flow."""
        files = await s3_storage_service.list_files(test_flow_id)
        assert files == []

    async def test_list_files_with_files(self, s3_storage_service, test_flow_id):
        """Test listing files in a flow with multiple files."""
        file_names = ["file1.txt", "file2.csv", "file3.json"]

        try:
            # Create files
            for file_name in file_names:
                await s3_storage_service.save_file(test_flow_id, file_name, b"content")

            # List files
            listed = await s3_storage_service.list_files(test_flow_id)

            assert len(listed) == 3
            assert set(listed) == set(file_names)
        finally:
            # Cleanup
            for file_name in file_names:
                with contextlib.suppress(Exception):
                    await s3_storage_service.delete_file(test_flow_id, file_name)

    async def test_list_files_excludes_other_flows(self, s3_storage_service, test_flow_id):
        """Test that list_files only returns files from the specified flow."""
        import uuid

        other_flow_id = f"test_flow_{uuid.uuid4().hex[:8]}"

        try:
            # Create file in test_flow_id
            await s3_storage_service.save_file(test_flow_id, "file1.txt", b"content1")

            # Create file in other_flow_id
            await s3_storage_service.save_file(other_flow_id, "file2.txt", b"content2")

            # List files for each flow
            files_flow1 = await s3_storage_service.list_files(test_flow_id)
            files_flow2 = await s3_storage_service.list_files(other_flow_id)

            # Verify isolation
            assert "file1.txt" in files_flow1
            assert "file1.txt" not in files_flow2
            assert "file2.txt" in files_flow2
            assert "file2.txt" not in files_flow1
        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, "file1.txt")
                await s3_storage_service.delete_file(other_flow_id, "file2.txt")


@pytest.mark.asyncio
class TestS3StorageServiceDeleteOperations:
    """Test delete operations in S3StorageService."""

    async def test_delete_existing_file(self, s3_storage_service, test_flow_id):
        """Test deleting an existing file."""
        file_name = "to_delete.txt"

        # Create file
        await s3_storage_service.save_file(test_flow_id, file_name, b"delete me")

        # Verify it exists
        files = await s3_storage_service.list_files(test_flow_id)
        assert file_name in files

        # Delete
        await s3_storage_service.delete_file(test_flow_id, file_name)

        # Verify it's gone
        with pytest.raises(FileNotFoundError):
            await s3_storage_service.get_file(test_flow_id, file_name)

    async def test_delete_nonexistent_file(self, s3_storage_service, test_flow_id):
        """Test deleting a non-existent file doesn't raise an error."""
        # S3 delete_object doesn't raise for non-existent files
        await s3_storage_service.delete_file(test_flow_id, "no_file.txt")

    async def test_delete_multiple_files(self, s3_storage_service, test_flow_id):
        """Test deleting multiple files."""
        files = ["file1.txt", "file2.txt", "file3.txt"]

        try:
            # Create files
            for file_name in files:
                await s3_storage_service.save_file(test_flow_id, file_name, b"content")

            # Delete all
            for file_name in files:
                await s3_storage_service.delete_file(test_flow_id, file_name)

            # Verify all gone
            listed = await s3_storage_service.list_files(test_flow_id)
            assert len(listed) == 0
        finally:
            # Cleanup any remaining
            for file_name in files:
                with contextlib.suppress(Exception):
                    await s3_storage_service.delete_file(test_flow_id, file_name)


@pytest.mark.asyncio
class TestS3StorageServiceFileSizeOperations:
    """Test file size operations in S3StorageService."""

    async def test_get_file_size(self, s3_storage_service, test_flow_id):
        """Test getting the size of a file."""
        file_name = "sized.txt"
        data = b"X" * 1234

        try:
            await s3_storage_service.save_file(test_flow_id, file_name, data)

            size = await s3_storage_service.get_file_size(test_flow_id, file_name)
            assert size == 1234
        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_size_empty_file(self, s3_storage_service, test_flow_id):
        """Test getting size of empty file."""
        file_name = "empty.txt"

        try:
            await s3_storage_service.save_file(test_flow_id, file_name, b"")

            size = await s3_storage_service.get_file_size(test_flow_id, file_name)
            assert size == 0
        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_size_nonexistent(self, s3_storage_service, test_flow_id):
        """Test getting size of non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await s3_storage_service.get_file_size(test_flow_id, "no_file.txt")


@pytest.mark.asyncio
class TestS3StorageServiceEdgeCases:
    """Test edge cases and special scenarios."""

    async def test_save_file_with_unicode_content(self, s3_storage_service, test_flow_id):
        """Test saving files with unicode content."""
        file_name = "unicode.txt"
        data = "Hello 世界 🌍".encode()

        try:
            await s3_storage_service.save_file(test_flow_id, file_name, data)
            retrieved = await s3_storage_service.get_file(test_flow_id, file_name)

            assert retrieved == data
            assert retrieved.decode("utf-8") == "Hello 世界 🌍"
        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)

    async def test_file_name_with_special_characters(self, s3_storage_service, test_flow_id):
        """Test files with special characters in names."""
        file_name = "test-file_2024.txt"
        data = b"special content"

        try:
            await s3_storage_service.save_file(test_flow_id, file_name, data)
            retrieved = await s3_storage_service.get_file(test_flow_id, file_name)

            assert retrieved == data
        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await s3_storage_service.delete_file(test_flow_id, file_name)

    async def test_concurrent_file_operations(self, s3_storage_service, test_flow_id):
        """Test concurrent file operations."""
        import asyncio

        file_names = [f"concurrent_{i}.txt" for i in range(5)]

        async def save_file(file_name):
            data = f"content_{file_name}".encode()
            await s3_storage_service.save_file(test_flow_id, file_name, data)

        try:
            # Save files concurrently
            await asyncio.gather(*[save_file(fn) for fn in file_names])

            # Verify all files exist
            listed = await s3_storage_service.list_files(test_flow_id)
            assert len(listed) == 5
            for file_name in file_names:
                assert file_name in listed
        finally:
            # Cleanup
            for file_name in file_names:
                with contextlib.suppress(Exception):
                    await s3_storage_service.delete_file(test_flow_id, file_name)


@pytest.mark.asyncio
class TestS3StorageServiceTeardown:
    """Test teardown operations in S3StorageService."""

    async def test_teardown(self, s3_storage_service):
        """Test that teardown completes without errors."""
        await s3_storage_service.teardown()

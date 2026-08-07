"""Integration tests for GCSStorageService using a real Google Cloud Storage bucket.

These tests use actual GCP credentials and interact with a real GCS bucket.
They are designed to be safe and clean up after themselves.

Credentials must be available via one of:
- GOOGLE_APPLICATION_CREDENTIALS (path to a service account JSON key file)
- Application Default Credentials (e.g. `gcloud auth application-default login`)
"""

import contextlib
import os
import uuid
from unittest.mock import Mock

import pytest
from langflow.services.storage.gcs import GCSStorageService

# Mark all tests in this module as requiring API keys
pytestmark = pytest.mark.api_key_required


@pytest.fixture
def _gcp_credentials():
    """Verify GCP credentials are available via environment variables."""
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        pytest.skip("Missing required environment variable: GOOGLE_APPLICATION_CREDENTIALS")


@pytest.fixture
def mock_settings_service():
    """Create a mock settings service with GCS configuration.

    Configuration via environment variables:
    - LANGFLOW_OBJECT_STORAGE_BUCKET_NAME: GCS bucket name (default: langflow-ci)
    - LANGFLOW_OBJECT_STORAGE_PREFIX: GCS prefix (default: test-files-gcs-1)
    """
    settings_service = Mock()
    settings_service.settings.config_dir = "/tmp/langflow_test"  # noqa: S108

    settings_service.settings.object_storage_bucket_name = os.environ.get(
        "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME", "langflow-ci"
    )
    settings_service.settings.object_storage_prefix = os.environ.get(
        "LANGFLOW_OBJECT_STORAGE_PREFIX", "test-files-gcs-1"
    )
    settings_service.settings.object_storage_tags = {}

    return settings_service


@pytest.fixture
def mock_session_service():
    """Create a mock session service."""
    return Mock()


@pytest.fixture
async def gcs_storage_service(mock_session_service, mock_settings_service, _gcp_credentials):
    """Create a GCSStorageService instance for testing with real GCS."""
    service = GCSStorageService(mock_session_service, mock_settings_service)
    yield service
    await service.teardown()


@pytest.fixture
def test_flow_id():
    """Unique flow ID for testing to avoid conflicts."""
    return f"test_flow_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
class TestGCSStorageServiceInitialization:
    """Test GCSStorageService initialization."""

    async def test_initialization(self, gcs_storage_service):
        """Test that the service initializes correctly and respects settings."""
        assert gcs_storage_service.ready is True

        expected_bucket = os.environ.get("LANGFLOW_OBJECT_STORAGE_BUCKET_NAME", "langflow-ci")
        assert gcs_storage_service.bucket_name == expected_bucket

        expected_prefix = os.environ.get("LANGFLOW_OBJECT_STORAGE_PREFIX", "test-files-gcs-1")
        assert gcs_storage_service.prefix == f"{expected_prefix}/"

    async def test_build_full_path(self, gcs_storage_service):
        """Test building full GCS object name with configured prefix."""
        expected_prefix = os.environ.get("LANGFLOW_OBJECT_STORAGE_PREFIX", "test-files-gcs-1")
        key = gcs_storage_service.build_full_path("flow_123", "test.txt")
        assert key == f"{expected_prefix}/flow_123/test.txt"

    async def test_resolve_component_path(self, gcs_storage_service):
        """Test that resolve_component_path returns logical path as-is."""
        logical_path = "flow_123/myfile.txt"
        resolved = gcs_storage_service.resolve_component_path(logical_path)
        assert resolved == logical_path


@pytest.mark.asyncio
class TestGCSStorageServiceFileOperations:
    """Test file operations in GCSStorageService with real GCS."""

    async def test_save_and_get_file(self, gcs_storage_service, test_flow_id):
        """Test saving and retrieving a file."""
        file_name = "test.txt"
        data = b"Hello, GCS!"

        try:
            await gcs_storage_service.save_file(test_flow_id, file_name, data)
            retrieved = await gcs_storage_service.get_file(test_flow_id, file_name)
            assert retrieved == data
        finally:
            with contextlib.suppress(Exception):
                await gcs_storage_service.delete_file(test_flow_id, file_name)

    async def test_save_file_overwrites_existing(self, gcs_storage_service, test_flow_id):
        """Test that saving a file overwrites existing content."""
        file_name = "overwrite.txt"

        try:
            await gcs_storage_service.save_file(test_flow_id, file_name, b"original")
            new_data = b"updated content"
            await gcs_storage_service.save_file(test_flow_id, file_name, new_data)

            retrieved = await gcs_storage_service.get_file(test_flow_id, file_name)
            assert retrieved == new_data
        finally:
            with contextlib.suppress(Exception):
                await gcs_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_not_found(self, gcs_storage_service, test_flow_id):
        """Test getting a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            await gcs_storage_service.get_file(test_flow_id, "nonexistent.txt")

    async def test_save_binary_file(self, gcs_storage_service, test_flow_id):
        """Test saving and retrieving binary data."""
        file_name = "binary.bin"
        data = bytes(range(256))

        try:
            await gcs_storage_service.save_file(test_flow_id, file_name, data)
            retrieved = await gcs_storage_service.get_file(test_flow_id, file_name)
            assert retrieved == data
        finally:
            with contextlib.suppress(Exception):
                await gcs_storage_service.delete_file(test_flow_id, file_name)

    async def test_save_large_file(self, gcs_storage_service, test_flow_id):
        """Test saving and retrieving a larger file (1MB)."""
        file_name = "large.bin"
        data = b"X" * (1024 * 1024)

        try:
            await gcs_storage_service.save_file(test_flow_id, file_name, data)

            size = await gcs_storage_service.get_file_size(test_flow_id, file_name)
            assert size == 1024 * 1024

            retrieved = await gcs_storage_service.get_file(test_flow_id, file_name)
            assert retrieved == data
        finally:
            with contextlib.suppress(Exception):
                await gcs_storage_service.delete_file(test_flow_id, file_name)


@pytest.mark.asyncio
class TestGCSStorageServiceStreamOperations:
    """Test streaming operations in GCSStorageService."""

    async def test_get_file_stream(self, gcs_storage_service, test_flow_id):
        """Test streaming a file from GCS."""
        file_name = "stream.txt"
        data = b"A" * 10000

        try:
            await gcs_storage_service.save_file(test_flow_id, file_name, data)

            chunks = [
                chunk async for chunk in gcs_storage_service.get_file_stream(test_flow_id, file_name, chunk_size=1024)
            ]

            streamed_data = b"".join(chunks)
            assert streamed_data == data
            assert len(chunks) > 1
        finally:
            with contextlib.suppress(Exception):
                await gcs_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_stream_not_found(self, gcs_storage_service, test_flow_id):
        """Test streaming a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            async for _ in gcs_storage_service.get_file_stream(test_flow_id, "no_file.txt"):
                pass


@pytest.mark.asyncio
class TestGCSStorageServiceListOperations:
    """Test list operations in GCSStorageService."""

    async def test_list_files_empty(self, gcs_storage_service, test_flow_id):
        """Test listing files in an empty flow."""
        files = await gcs_storage_service.list_files(test_flow_id)
        assert files == []

    async def test_list_files_with_files(self, gcs_storage_service, test_flow_id):
        """Test listing files in a flow with multiple files."""
        file_names = ["file1.txt", "file2.csv", "file3.json"]

        try:
            for file_name in file_names:
                await gcs_storage_service.save_file(test_flow_id, file_name, b"content")

            listed = await gcs_storage_service.list_files(test_flow_id)

            assert len(listed) == 3
            assert set(listed) == set(file_names)
        finally:
            for file_name in file_names:
                with contextlib.suppress(Exception):
                    await gcs_storage_service.delete_file(test_flow_id, file_name)

    async def test_list_files_excludes_other_flows(self, gcs_storage_service, test_flow_id):
        """Test that list_files only returns files from the specified flow."""
        other_flow_id = f"test_flow_{uuid.uuid4().hex[:8]}"

        try:
            await gcs_storage_service.save_file(test_flow_id, "file1.txt", b"content1")
            await gcs_storage_service.save_file(other_flow_id, "file2.txt", b"content2")

            files_flow1 = await gcs_storage_service.list_files(test_flow_id)
            files_flow2 = await gcs_storage_service.list_files(other_flow_id)

            assert "file1.txt" in files_flow1
            assert "file1.txt" not in files_flow2
            assert "file2.txt" in files_flow2
            assert "file2.txt" not in files_flow1
        finally:
            with contextlib.suppress(Exception):
                await gcs_storage_service.delete_file(test_flow_id, "file1.txt")
                await gcs_storage_service.delete_file(other_flow_id, "file2.txt")


@pytest.mark.asyncio
class TestGCSStorageServiceDeleteOperations:
    """Test delete operations in GCSStorageService."""

    async def test_delete_existing_file(self, gcs_storage_service, test_flow_id):
        """Test deleting an existing file."""
        file_name = "to_delete.txt"

        await gcs_storage_service.save_file(test_flow_id, file_name, b"delete me")

        files = await gcs_storage_service.list_files(test_flow_id)
        assert file_name in files

        await gcs_storage_service.delete_file(test_flow_id, file_name)

        with pytest.raises(FileNotFoundError):
            await gcs_storage_service.get_file(test_flow_id, file_name)

    async def test_delete_nonexistent_file(self, gcs_storage_service, test_flow_id):
        """Test deleting a non-existent file doesn't raise an error."""
        # Matches S3/local backend semantics: deleting a missing key is a no-op.
        await gcs_storage_service.delete_file(test_flow_id, "no_file.txt")


@pytest.mark.asyncio
class TestGCSStorageServiceFileSizeOperations:
    """Test file size operations in GCSStorageService."""

    async def test_get_file_size(self, gcs_storage_service, test_flow_id):
        """Test getting the size of a file."""
        file_name = "sized.txt"
        data = b"X" * 1234

        try:
            await gcs_storage_service.save_file(test_flow_id, file_name, data)

            size = await gcs_storage_service.get_file_size(test_flow_id, file_name)
            assert size == 1234
        finally:
            with contextlib.suppress(Exception):
                await gcs_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_size_empty_file(self, gcs_storage_service, test_flow_id):
        """Test getting size of empty file."""
        file_name = "empty.txt"

        try:
            await gcs_storage_service.save_file(test_flow_id, file_name, b"")

            size = await gcs_storage_service.get_file_size(test_flow_id, file_name)
            assert size == 0
        finally:
            with contextlib.suppress(Exception):
                await gcs_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_size_nonexistent(self, gcs_storage_service, test_flow_id):
        """Test getting size of non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await gcs_storage_service.get_file_size(test_flow_id, "no_file.txt")


@pytest.mark.asyncio
class TestGCSStorageServiceEdgeCases:
    """Test edge cases and special scenarios."""

    async def test_save_file_with_unicode_content(self, gcs_storage_service, test_flow_id):
        """Test saving files with unicode content."""
        file_name = "unicode.txt"
        data = "Hello 世界 🌍".encode()

        try:
            await gcs_storage_service.save_file(test_flow_id, file_name, data)
            retrieved = await gcs_storage_service.get_file(test_flow_id, file_name)

            assert retrieved == data
            assert retrieved.decode("utf-8") == "Hello 世界 🌍"
        finally:
            with contextlib.suppress(Exception):
                await gcs_storage_service.delete_file(test_flow_id, file_name)

    async def test_concurrent_file_operations(self, gcs_storage_service, test_flow_id):
        """Test concurrent file operations."""
        import asyncio

        file_names = [f"concurrent_{i}.txt" for i in range(5)]

        async def save_file(file_name):
            data = f"content_{file_name}".encode()
            await gcs_storage_service.save_file(test_flow_id, file_name, data)

        try:
            await asyncio.gather(*[save_file(fn) for fn in file_names])

            listed = await gcs_storage_service.list_files(test_flow_id)
            assert len(listed) == 5
            for file_name in file_names:
                assert file_name in listed
        finally:
            for file_name in file_names:
                with contextlib.suppress(Exception):
                    await gcs_storage_service.delete_file(test_flow_id, file_name)


@pytest.mark.asyncio
class TestGCSStorageServiceTeardown:
    """Test teardown operations in GCSStorageService."""

    async def test_teardown(self, gcs_storage_service):
        """Test that teardown completes without errors."""
        await gcs_storage_service.teardown()

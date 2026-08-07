"""Integration tests for AzureBlobStorageService using a real Azure Blob Storage container.

These tests use actual Azure credentials and interact with a real Blob Storage
container (or an ADLS Gen2 account, which remains Blob-API compatible). They are
designed to be safe and clean up after themselves.

Credentials must be available via one of:
- AZURE_STORAGE_CONNECTION_STRING
- AZURE_STORAGE_ACCOUNT_URL or AZURE_STORAGE_ACCOUNT_NAME, with credentials resolvable
  via DefaultAzureCredential (managed identity, workload identity, service principal,
  or `az login`)
"""

import contextlib
import os
import uuid
from unittest.mock import Mock

import pytest
from langflow.services.storage.azure_blob import AzureBlobStorageService

# Mark all tests in this module as requiring API keys
pytestmark = pytest.mark.api_key_required


@pytest.fixture
def _azure_credentials():
    """Verify Azure credentials are available via environment variables."""
    has_connection_string = bool(os.environ.get("AZURE_STORAGE_CONNECTION_STRING"))
    has_account = bool(os.environ.get("AZURE_STORAGE_ACCOUNT_URL") or os.environ.get("AZURE_STORAGE_ACCOUNT_NAME"))
    if not (has_connection_string or has_account):
        pytest.skip(
            "Missing required environment variables: AZURE_STORAGE_CONNECTION_STRING, or "
            "AZURE_STORAGE_ACCOUNT_URL / AZURE_STORAGE_ACCOUNT_NAME"
        )


@pytest.fixture
def mock_settings_service():
    """Create a mock settings service with Azure Blob configuration.

    Configuration via environment variables:
    - LANGFLOW_OBJECT_STORAGE_BUCKET_NAME: Azure Blob container name (default: langflow-ci)
    - LANGFLOW_OBJECT_STORAGE_PREFIX: Azure Blob prefix (default: test-files-azure-1)
    """
    settings_service = Mock()
    settings_service.settings.config_dir = "/tmp/langflow_test"  # noqa: S108

    settings_service.settings.object_storage_bucket_name = os.environ.get(
        "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME", "langflow-ci"
    )
    settings_service.settings.object_storage_prefix = os.environ.get(
        "LANGFLOW_OBJECT_STORAGE_PREFIX", "test-files-azure-1"
    )
    settings_service.settings.object_storage_tags = {}

    return settings_service


@pytest.fixture
def mock_session_service():
    """Create a mock session service."""
    return Mock()


@pytest.fixture
async def azure_storage_service(mock_session_service, mock_settings_service, _azure_credentials):
    """Create an AzureBlobStorageService instance for testing with real Azure Blob storage."""
    service = AzureBlobStorageService(mock_session_service, mock_settings_service)
    yield service
    await service.teardown()


@pytest.fixture
def test_flow_id():
    """Unique flow ID for testing to avoid conflicts."""
    return f"test_flow_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
class TestAzureBlobStorageServiceInitialization:
    """Test AzureBlobStorageService initialization."""

    async def test_initialization(self, azure_storage_service):
        """Test that the service initializes correctly and respects settings."""
        assert azure_storage_service.ready is True

        expected_container = os.environ.get("LANGFLOW_OBJECT_STORAGE_BUCKET_NAME", "langflow-ci")
        assert azure_storage_service.container_name == expected_container

        expected_prefix = os.environ.get("LANGFLOW_OBJECT_STORAGE_PREFIX", "test-files-azure-1")
        assert azure_storage_service.prefix == f"{expected_prefix}/"

    async def test_build_full_path(self, azure_storage_service):
        """Test building full Azure blob name with configured prefix."""
        expected_prefix = os.environ.get("LANGFLOW_OBJECT_STORAGE_PREFIX", "test-files-azure-1")
        key = azure_storage_service.build_full_path("flow_123", "test.txt")
        assert key == f"{expected_prefix}/flow_123/test.txt"

    async def test_resolve_component_path(self, azure_storage_service):
        """Test that resolve_component_path returns logical path as-is."""
        logical_path = "flow_123/myfile.txt"
        resolved = azure_storage_service.resolve_component_path(logical_path)
        assert resolved == logical_path


@pytest.mark.asyncio
class TestAzureBlobStorageServiceFileOperations:
    """Test file operations in AzureBlobStorageService with real Azure Blob storage."""

    async def test_save_and_get_file(self, azure_storage_service, test_flow_id):
        """Test saving and retrieving a file."""
        file_name = "test.txt"
        data = b"Hello, Azure!"

        try:
            await azure_storage_service.save_file(test_flow_id, file_name, data)
            retrieved = await azure_storage_service.get_file(test_flow_id, file_name)
            assert retrieved == data
        finally:
            with contextlib.suppress(Exception):
                await azure_storage_service.delete_file(test_flow_id, file_name)

    async def test_save_file_overwrites_existing(self, azure_storage_service, test_flow_id):
        """Test that saving a file overwrites existing content."""
        file_name = "overwrite.txt"

        try:
            await azure_storage_service.save_file(test_flow_id, file_name, b"original")
            new_data = b"updated content"
            await azure_storage_service.save_file(test_flow_id, file_name, new_data)

            retrieved = await azure_storage_service.get_file(test_flow_id, file_name)
            assert retrieved == new_data
        finally:
            with contextlib.suppress(Exception):
                await azure_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_not_found(self, azure_storage_service, test_flow_id):
        """Test getting a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            await azure_storage_service.get_file(test_flow_id, "nonexistent.txt")

    async def test_save_binary_file(self, azure_storage_service, test_flow_id):
        """Test saving and retrieving binary data."""
        file_name = "binary.bin"
        data = bytes(range(256))

        try:
            await azure_storage_service.save_file(test_flow_id, file_name, data)
            retrieved = await azure_storage_service.get_file(test_flow_id, file_name)
            assert retrieved == data
        finally:
            with contextlib.suppress(Exception):
                await azure_storage_service.delete_file(test_flow_id, file_name)

    async def test_save_large_file(self, azure_storage_service, test_flow_id):
        """Test saving and retrieving a larger file (1MB)."""
        file_name = "large.bin"
        data = b"X" * (1024 * 1024)

        try:
            await azure_storage_service.save_file(test_flow_id, file_name, data)

            size = await azure_storage_service.get_file_size(test_flow_id, file_name)
            assert size == 1024 * 1024

            retrieved = await azure_storage_service.get_file(test_flow_id, file_name)
            assert retrieved == data
        finally:
            with contextlib.suppress(Exception):
                await azure_storage_service.delete_file(test_flow_id, file_name)


@pytest.mark.asyncio
class TestAzureBlobStorageServiceStreamOperations:
    """Test streaming operations in AzureBlobStorageService."""

    async def test_get_file_stream(self, azure_storage_service, test_flow_id):
        """Test streaming a file from Azure Blob storage."""
        file_name = "stream.txt"
        data = b"A" * 10000

        try:
            await azure_storage_service.save_file(test_flow_id, file_name, data)

            chunks = [
                chunk async for chunk in azure_storage_service.get_file_stream(test_flow_id, file_name, chunk_size=1024)
            ]

            streamed_data = b"".join(chunks)
            assert streamed_data == data
            assert len(chunks) > 1
        finally:
            with contextlib.suppress(Exception):
                await azure_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_stream_not_found(self, azure_storage_service, test_flow_id):
        """Test streaming a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            async for _ in azure_storage_service.get_file_stream(test_flow_id, "no_file.txt"):
                pass


@pytest.mark.asyncio
class TestAzureBlobStorageServiceListOperations:
    """Test list operations in AzureBlobStorageService."""

    async def test_list_files_empty(self, azure_storage_service, test_flow_id):
        """Test listing files in an empty flow."""
        files = await azure_storage_service.list_files(test_flow_id)
        assert files == []

    async def test_list_files_with_files(self, azure_storage_service, test_flow_id):
        """Test listing files in a flow with multiple files."""
        file_names = ["file1.txt", "file2.csv", "file3.json"]

        try:
            for file_name in file_names:
                await azure_storage_service.save_file(test_flow_id, file_name, b"content")

            listed = await azure_storage_service.list_files(test_flow_id)

            assert len(listed) == 3
            assert set(listed) == set(file_names)
        finally:
            for file_name in file_names:
                with contextlib.suppress(Exception):
                    await azure_storage_service.delete_file(test_flow_id, file_name)

    async def test_list_files_excludes_other_flows(self, azure_storage_service, test_flow_id):
        """Test that list_files only returns files from the specified flow."""
        other_flow_id = f"test_flow_{uuid.uuid4().hex[:8]}"

        try:
            await azure_storage_service.save_file(test_flow_id, "file1.txt", b"content1")
            await azure_storage_service.save_file(other_flow_id, "file2.txt", b"content2")

            files_flow1 = await azure_storage_service.list_files(test_flow_id)
            files_flow2 = await azure_storage_service.list_files(other_flow_id)

            assert "file1.txt" in files_flow1
            assert "file1.txt" not in files_flow2
            assert "file2.txt" in files_flow2
            assert "file2.txt" not in files_flow1
        finally:
            with contextlib.suppress(Exception):
                await azure_storage_service.delete_file(test_flow_id, "file1.txt")
                await azure_storage_service.delete_file(other_flow_id, "file2.txt")


@pytest.mark.asyncio
class TestAzureBlobStorageServiceDeleteOperations:
    """Test delete operations in AzureBlobStorageService."""

    async def test_delete_existing_file(self, azure_storage_service, test_flow_id):
        """Test deleting an existing file."""
        file_name = "to_delete.txt"

        await azure_storage_service.save_file(test_flow_id, file_name, b"delete me")

        files = await azure_storage_service.list_files(test_flow_id)
        assert file_name in files

        await azure_storage_service.delete_file(test_flow_id, file_name)

        with pytest.raises(FileNotFoundError):
            await azure_storage_service.get_file(test_flow_id, file_name)

    async def test_delete_nonexistent_file(self, azure_storage_service, test_flow_id):
        """Test deleting a non-existent file doesn't raise an error."""
        # Matches S3/GCS/local backend semantics: deleting a missing blob is a no-op.
        await azure_storage_service.delete_file(test_flow_id, "no_file.txt")


@pytest.mark.asyncio
class TestAzureBlobStorageServiceFileSizeOperations:
    """Test file size operations in AzureBlobStorageService."""

    async def test_get_file_size(self, azure_storage_service, test_flow_id):
        """Test getting the size of a file."""
        file_name = "sized.txt"
        data = b"X" * 1234

        try:
            await azure_storage_service.save_file(test_flow_id, file_name, data)

            size = await azure_storage_service.get_file_size(test_flow_id, file_name)
            assert size == 1234
        finally:
            with contextlib.suppress(Exception):
                await azure_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_size_empty_file(self, azure_storage_service, test_flow_id):
        """Test getting size of empty file."""
        file_name = "empty.txt"

        try:
            await azure_storage_service.save_file(test_flow_id, file_name, b"")

            size = await azure_storage_service.get_file_size(test_flow_id, file_name)
            assert size == 0
        finally:
            with contextlib.suppress(Exception):
                await azure_storage_service.delete_file(test_flow_id, file_name)

    async def test_get_file_size_nonexistent(self, azure_storage_service, test_flow_id):
        """Test getting size of non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await azure_storage_service.get_file_size(test_flow_id, "no_file.txt")


@pytest.mark.asyncio
class TestAzureBlobStorageServiceEdgeCases:
    """Test edge cases and special scenarios."""

    async def test_save_file_with_unicode_content(self, azure_storage_service, test_flow_id):
        """Test saving files with unicode content."""
        file_name = "unicode.txt"
        data = "Hello 世界 🌍".encode()

        try:
            await azure_storage_service.save_file(test_flow_id, file_name, data)
            retrieved = await azure_storage_service.get_file(test_flow_id, file_name)

            assert retrieved == data
            assert retrieved.decode("utf-8") == "Hello 世界 🌍"
        finally:
            with contextlib.suppress(Exception):
                await azure_storage_service.delete_file(test_flow_id, file_name)

    async def test_concurrent_file_operations(self, azure_storage_service, test_flow_id):
        """Test concurrent file operations."""
        import asyncio

        file_names = [f"concurrent_{i}.txt" for i in range(5)]

        async def save_file(file_name):
            data = f"content_{file_name}".encode()
            await azure_storage_service.save_file(test_flow_id, file_name, data)

        try:
            await asyncio.gather(*[save_file(fn) for fn in file_names])

            listed = await azure_storage_service.list_files(test_flow_id)
            assert len(listed) == 5
            for file_name in file_names:
                assert file_name in listed
        finally:
            for file_name in file_names:
                with contextlib.suppress(Exception):
                    await azure_storage_service.delete_file(test_flow_id, file_name)


@pytest.mark.asyncio
class TestAzureBlobStorageServiceTeardown:
    """Test teardown operations in AzureBlobStorageService."""

    async def test_teardown(self, azure_storage_service):
        """Test that teardown completes without errors."""
        await azure_storage_service.teardown()

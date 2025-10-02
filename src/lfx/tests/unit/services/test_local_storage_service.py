"""Unit tests for LocalStorageService new methods."""

from pathlib import Path

import pytest

from lfx.services.storage.local import LocalStorageService


class TestLocalStorageServiceNewMethods:
    """Test cases for new unified storage methods in LocalStorageService."""

    @pytest.fixture
    def storage_service(self, tmp_path):
        """Create a LocalStorageService instance with temporary directory."""
        service = LocalStorageService(data_dir=tmp_path)
        return service

    @pytest.fixture
    def test_file_content(self):
        """Test file content."""
        return b"Hello, World! This is test content."

    # Tests for is_remote_path
    def test_is_remote_path_always_false(self, storage_service):
        """Test that is_remote_path always returns False for local storage."""
        assert storage_service.is_remote_path("/local/path/file.txt") is False
        assert storage_service.is_remote_path("s3://bucket/file.txt") is False
        assert storage_service.is_remote_path("relative/path.txt") is False
        assert storage_service.is_remote_path("") is False

    # Tests for parse_path
    def test_parse_path_absolute_within_data_dir(self, storage_service):
        """Test parsing absolute path within data_dir."""
        test_path = storage_service.data_dir / "flow-123" / "document.pdf"
        flow_id, file_name = storage_service.parse_path(str(test_path))

        assert flow_id == "flow-123"
        assert file_name == "document.pdf"

    def test_parse_path_absolute_nested_file(self, storage_service):
        """Test parsing absolute path with nested directories."""
        test_path = storage_service.data_dir / "flow-456" / "subfolder" / "file.txt"
        flow_id, file_name = storage_service.parse_path(str(test_path))

        assert flow_id == "flow-456"
        assert file_name == "subfolder/file.txt"

    def test_parse_path_absolute_outside_data_dir(self, storage_service):
        """Test parsing absolute path outside data_dir defaults to 'local'."""
        test_path = "/completely/different/path/file.txt"
        flow_id, file_name = storage_service.parse_path(test_path)

        assert flow_id == "local"
        assert file_name == "file.txt"

    def test_parse_path_relative_path(self, storage_service):
        """Test parsing relative path defaults to 'local'."""
        flow_id, file_name = storage_service.parse_path("relative/path/file.txt")

        assert flow_id == "local"
        assert file_name == "file.txt"

    def test_parse_path_filename_only(self, storage_service):
        """Test parsing just a filename defaults to 'local'."""
        flow_id, file_name = storage_service.parse_path("document.pdf")

        assert flow_id == "local"
        assert file_name == "document.pdf"

    def test_parse_path_invalid_input(self, storage_service):
        """Test parsing invalid input returns None."""
        assert storage_service.parse_path("") is None
        assert storage_service.parse_path(None) is None

    def test_parse_path_single_level_in_data_dir(self, storage_service):
        """Test parsing path with single level in data_dir."""
        test_path = storage_service.data_dir / "file.txt"
        flow_id, file_name = storage_service.parse_path(str(test_path))

        assert flow_id == "local"
        assert file_name == "file.txt"

    # Tests for path_exists
    @pytest.mark.asyncio
    async def test_path_exists_true(self, storage_service, test_file_content):
        """Test path_exists returns True for existing file."""
        # Create test file
        await storage_service.save_file("test-flow", "test.txt", test_file_content)

        # Check if it exists
        exists = await storage_service.path_exists("test-flow", "test.txt")
        assert exists is True

    @pytest.mark.asyncio
    async def test_path_exists_false(self, storage_service):
        """Test path_exists returns False for non-existent file."""
        exists = await storage_service.path_exists("test-flow", "nonexistent.txt")
        assert exists is False

    @pytest.mark.asyncio
    async def test_path_exists_missing_flow_id(self, storage_service):
        """Test path_exists returns False for non-existent flow."""
        exists = await storage_service.path_exists("nonexistent-flow", "test.txt")
        assert exists is False

    # Tests for read_file
    @pytest.mark.asyncio
    async def test_read_file_success(self, storage_service, test_file_content):
        """Test reading file through unified interface."""
        # Create test file
        await storage_service.save_file("flow-123", "document.pdf", test_file_content)

        # Build path and read
        file_path = storage_service.build_full_path("flow-123", "document.pdf")
        content = await storage_service.read_file(file_path)

        assert content == test_file_content

    @pytest.mark.asyncio
    async def test_read_file_with_relative_path(self, storage_service, test_file_content):
        """Test reading file with relative path (defaults to 'local' flow)."""
        # Create test file in 'local' flow
        await storage_service.save_file("local", "test.txt", test_file_content)

        # Read with just filename
        content = await storage_service.read_file("test.txt")

        assert content == test_file_content

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, storage_service):
        """Test reading non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await storage_service.read_file("/path/to/nonexistent.txt")

    @pytest.mark.asyncio
    async def test_read_file_invalid_path(self, storage_service):
        """Test reading file with invalid path raises ValueError."""
        with pytest.raises(ValueError, match="Invalid path format"):
            await storage_service.read_file("")

    # Tests for write_file
    @pytest.mark.asyncio
    async def test_write_file_with_full_path(self, storage_service, test_file_content):
        """Test writing file with full path."""
        file_path = storage_service.build_full_path("flow-789", "new.txt")
        result_path = await storage_service.write_file(file_path, test_file_content)

        # Verify file was written
        assert result_path == file_path
        content = await storage_service.get_file("flow-789", "new.txt")
        assert content == test_file_content

    @pytest.mark.asyncio
    async def test_write_file_with_explicit_flow_id(self, storage_service, test_file_content):
        """Test writing file with explicit flow_id parameter."""
        result_path = await storage_service.write_file("document.pdf", test_file_content, flow_id="my-flow")

        # Verify file was written to specified flow
        expected_path = storage_service.build_full_path("my-flow", "document.pdf")
        assert result_path == expected_path

        content = await storage_service.get_file("my-flow", "document.pdf")
        assert content == test_file_content

    @pytest.mark.asyncio
    async def test_write_file_with_relative_path(self, storage_service, test_file_content):
        """Test writing file with relative path (defaults to 'local')."""
        result_path = await storage_service.write_file("test.txt", test_file_content)

        # Should default to 'local' flow
        content = await storage_service.get_file("local", "test.txt")
        assert content == test_file_content

    @pytest.mark.asyncio
    async def test_write_file_overwrites_existing(self, storage_service):
        """Test writing file overwrites existing content."""
        # Write initial content
        await storage_service.write_file("test.txt", b"initial content", flow_id="flow-1")

        # Overwrite with new content
        await storage_service.write_file("test.txt", b"new content", flow_id="flow-1")

        # Verify new content
        content = await storage_service.get_file("flow-1", "test.txt")
        assert content == b"new content"

    @pytest.mark.asyncio
    async def test_write_file_creates_directories(self, storage_service, test_file_content):
        """Test writing file creates necessary directories."""
        result_path = await storage_service.write_file("test.txt", test_file_content, flow_id="new-flow")

        # Verify directory was created
        flow_dir = storage_service.data_dir / "new-flow"
        assert flow_dir.exists()
        assert flow_dir.is_dir()

    @pytest.mark.asyncio
    async def test_write_file_empty_content(self, storage_service):
        """Test writing empty file."""
        result_path = await storage_service.write_file("empty.txt", b"", flow_id="test-flow")

        content = await storage_service.get_file("test-flow", "empty.txt")
        assert content == b""

    @pytest.mark.asyncio
    async def test_write_file_invalid_path(self, storage_service):
        """Test writing file with invalid path raises ValueError."""
        with pytest.raises(ValueError, match="Invalid path format"):
            await storage_service.write_file("", b"content")

    # Integration tests combining multiple methods
    @pytest.mark.asyncio
    async def test_workflow_write_check_read(self, storage_service, test_file_content):
        """Test complete workflow: write, check existence, read."""
        flow_id = "integration-flow"
        file_name = "workflow.txt"

        # Write file
        file_path = await storage_service.write_file(file_name, test_file_content, flow_id=flow_id)

        # Check existence
        exists = await storage_service.path_exists(flow_id, file_name)
        assert exists is True

        # Read file
        content = await storage_service.read_file(file_path)
        assert content == test_file_content

    @pytest.mark.asyncio
    async def test_parse_and_read_consistency(self, storage_service, test_file_content):
        """Test that parse_path and read_file work consistently together."""
        # Write file
        await storage_service.save_file("flow-abc", "doc.pdf", test_file_content)

        # Build full path
        full_path = storage_service.build_full_path("flow-abc", "doc.pdf")

        # Parse it back
        parsed_flow, parsed_file = storage_service.parse_path(full_path)
        assert parsed_flow == "flow-abc"
        assert parsed_file == "doc.pdf"

        # Read using full path
        content = await storage_service.read_file(full_path)
        assert content == test_file_content

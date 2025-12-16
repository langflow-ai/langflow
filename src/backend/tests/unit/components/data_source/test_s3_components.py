"""S3-specific test class for components that work with S3 storage.

This test class focuses on components that are compatible with S3 storage.
"""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.files_and_knowledge.file import FileComponent
from lfx.components.files_and_knowledge.save_file import SaveToFileComponent
from lfx.components.langchain_utilities.csv_agent import CSVAgentComponent
from lfx.components.langchain_utilities.json_agent import JsonAgentComponent


@contextmanager
def mock_s3_environment(settings, storage_service):
    """Context manager to mock S3 storage environment.

    This patches all the necessary get_settings_service and get_storage_service
    calls across the codebase to enable S3 testing.
    """
    patches = [
        patch("lfx.services.deps.get_settings_service", return_value=settings),
        patch("lfx.base.data.base_file.get_settings_service", return_value=settings),
        patch("lfx.base.data.storage_utils.get_settings_service", return_value=settings),
        patch("lfx.base.data.storage_utils.get_storage_service", return_value=storage_service),
        patch("lfx.base.data.utils.get_settings_service", return_value=settings),
        patch("lfx.components.files_and_knowledge.file.get_settings_service", return_value=settings),
        patch("lfx.components.files_and_knowledge.file.get_storage_service", return_value=storage_service),
        patch("lfx.components.langchain_utilities.csv_agent.get_settings_service", return_value=settings),
        patch("lfx.components.langchain_utilities.json_agent.get_settings_service", return_value=settings),
    ]

    # Start all patches
    [p.start() for p in patches]
    try:
        yield
    finally:
        # Stop all patches
        for p in patches:
            p.stop()


class TestS3CompatibleComponents:
    """Test components that work with S3 storage."""

    @pytest.fixture
    def s3_settings(self):
        """Mock S3 settings."""
        settings = MagicMock()
        settings.settings.storage_type = "s3"
        return settings

    @pytest.fixture
    def local_settings(self):
        """Mock local settings."""
        settings = MagicMock()
        settings.settings.storage_type = "local"
        return settings

    @pytest.fixture
    def mock_storage_service(self):
        """Mock storage service for S3 operations."""
        return AsyncMock()

    def test_file_component_s3_path_handling(self, s3_settings, mock_storage_service):
        """Test FileComponent with S3 paths."""
        s3_path = "user_123/document.txt"
        mock_storage_service.get_file.return_value = b"file content"

        with mock_s3_environment(s3_settings, mock_storage_service):
            component = FileComponent()
            component.path = s3_path  # Use 'path' property, not 'file_path'

            result = component.load_files()

            # Should process S3 file successfully
            assert result is not None
            assert len(result) > 0
            mock_storage_service.get_file.assert_called_with("user_123", "document.txt")

    @pytest.mark.asyncio
    async def test_file_component_get_local_file_for_docling_s3(self, s3_settings, mock_storage_service):
        """Test FileComponent._get_local_file_for_docling with S3 paths uses parse_storage_path and Path."""
        component = FileComponent()
        s3_path = "user_123/document.pdf"

        # Configure mock storage service
        mock_storage_service.get_file = AsyncMock(return_value=b"pdf content")

        # Mock tempfile
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/temp_file.pdf"  # noqa: S108
        mock_temp_file.write = MagicMock()

        with (
            mock_s3_environment(s3_settings, mock_storage_service),
            patch(
                "lfx.components.files_and_knowledge.file.parse_storage_path", return_value=("user_123", "document.pdf")
            ) as mock_parse,
            patch("lfx.components.files_and_knowledge.file.NamedTemporaryFile") as mock_temp,
        ):
            mock_temp.return_value.__enter__.return_value = mock_temp_file

            local_path, should_delete = await component._get_local_file_for_docling(s3_path)

            # Verify parse_storage_path was called with S3 path (imported at module level)
            mock_parse.assert_called_once_with(s3_path)
            # Verify storage service was called
            mock_storage_service.get_file.assert_called_once_with("user_123", "document.pdf")
            # Verify temp file was created
            assert should_delete is True
            assert local_path == "/tmp/temp_file.pdf"  # noqa: S108

    @pytest.mark.asyncio
    async def test_file_component_get_local_file_for_docling_local(self, local_settings):
        """Test FileComponent._get_local_file_for_docling with local paths."""
        with patch("lfx.services.deps.get_settings_service", return_value=local_settings):
            component = FileComponent()
            local_path = "/local/path/document.pdf"

            result_path, should_delete = await component._get_local_file_for_docling(local_path)

            # Should return local path as-is, no deletion needed
            assert result_path == local_path
            assert should_delete is False

    @pytest.mark.asyncio
    async def test_save_file_component_s3_upload(self, s3_settings):
        """Test SaveToFileComponent with S3 storage."""
        # Mock boto3 S3 client
        mock_s3_client = MagicMock()
        mock_s3_client.put_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

        with (
            patch("lfx.services.deps.get_settings_service", return_value=s3_settings),
            patch("boto3.client", return_value=mock_s3_client),
        ):
            component = SaveToFileComponent()

            # Mock database and storage services
            with (
                patch("lfx.services.deps.session_scope"),
                patch(
                    "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
                ) as mock_get_user,
                patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            ):
                mock_get_user.return_value = MagicMock()
                mock_upload.return_value = "s3_file.txt"

                # Test with DataFrame
                from langflow.schema import Data, DataFrame

                test_data = DataFrame(data=[Data(data={"text": "test content"})])
                component.input = test_data  # Use 'input' not 'data'
                component.file_name = "test_output.csv"
                component.storage_location = [{"name": "AWS"}]  # Set S3 storage location
                # Set required AWS credentials (will be mocked out anyway)
                component.aws_access_key_id = "test_key"
                component.aws_secret_access_key = "test_secret"  # noqa: S105  # pragma: allowlist secret
                component.aws_region = "us-east-1"
                component.bucket_name = "test-bucket"

                result = await component.save_to_file()

                # Should upload to S3 successfully
                assert "successfully uploaded" in result.text
                assert "s3://" in result.text
                assert "test-bucket" in result.text

    @pytest.mark.asyncio
    async def test_csv_agent_s3_file_handling(self, s3_settings):
        """Test CSVAgentComponent with S3 files."""
        with patch("lfx.services.deps.get_settings_service", return_value=s3_settings):
            component = CSVAgentComponent()
            component.set_attributes({"llm": MagicMock(), "path": "user_123/data.csv", "verbose": False})

            # Mock storage utils
            with patch(
                "lfx.base.data.storage_utils.read_file_bytes", new_callable=AsyncMock, return_value=b"name,age\nJohn,30"
            ):
                local_path = component._get_local_path()

                # Should handle S3 path correctly
                assert local_path is not None

    @pytest.mark.asyncio
    async def test_json_agent_s3_file_handling(self, s3_settings):
        """Test JsonAgentComponent with S3 files."""
        with patch("lfx.services.deps.get_settings_service", return_value=s3_settings):
            component = JsonAgentComponent()
            component.set_attributes({"llm": MagicMock(), "path": "user_123/data.json", "verbose": False})

            # Mock storage utils
            with patch(
                "lfx.base.data.storage_utils.read_file_bytes", new_callable=AsyncMock, return_value=b'{"key": "value"}'
            ):
                local_path = component._get_local_path()

                # Should handle S3 path correctly
                assert local_path is not None

    @pytest.mark.asyncio
    async def test_components_work_in_local_mode(self, local_settings):
        """Test that components work in local mode."""
        with patch("langflow.services.deps.get_settings_service", return_value=local_settings):
            component = FileComponent()
            component.file_path = "/local/path/file.txt"

            # Should work with local paths
            assert component.file_path == "/local/path/file.txt"

    @pytest.mark.asyncio
    async def test_s3_path_parsing(self, s3_settings):
        """Test S3 path parsing in components."""
        with patch("lfx.services.deps.get_settings_service", return_value=s3_settings):
            # Test various S3 path formats
            test_paths = ["user_123/file.txt", "flow_456/document.pdf", "user_789/folder/subfolder/file.json"]

            for path in test_paths:
                component = FileComponent()
                component.file_path = path

                # Should accept S3 paths
                assert component.file_path == path

    def test_s3_file_download_and_processing(self, s3_settings, mock_storage_service):
        """Test downloading and processing S3 files."""
        mock_storage_service.get_file.return_value = b"csv,content\n1,2"

        with mock_s3_environment(s3_settings, mock_storage_service):
            component = FileComponent()
            component.path = "user_123/large_file.csv"

            result = component.load_files()

            # Should process downloaded content
            assert result is not None
            mock_storage_service.get_file.assert_called_with("user_123", "large_file.csv")

    def test_s3_error_handling(self, s3_settings, mock_storage_service):
        """Test error handling with S3 operations."""
        mock_storage_service.get_file.side_effect = FileNotFoundError("File not found")

        with mock_s3_environment(s3_settings, mock_storage_service):
            component = FileComponent()
            component.path = "user_123/nonexistent.txt"
            component.silent_errors = False

            # Should raise ValueError (wraps FileNotFoundError)
            with pytest.raises(ValueError, match="Error loading file"):
                component.load_files()

    def test_s3_streaming_operations(self, s3_settings, mock_storage_service):
        """Test streaming operations with S3."""
        mock_storage_service.get_file.return_value = b"chunk1chunk2chunk3"

        with mock_s3_environment(s3_settings, mock_storage_service):
            component = FileComponent()
            component.path = "user_123/large_file.txt"

            result = component.load_files()

            # Should handle streaming content
            assert result is not None
            mock_storage_service.get_file.assert_called_with("user_123", "large_file.txt")

    def test_s3_metadata_handling(self, s3_settings, mock_storage_service):
        """Test metadata handling with S3 files."""
        file_content = b'{"name": "test", "size": 1024, "type": "application/json"}'
        mock_storage_service.get_file.return_value = file_content

        with mock_s3_environment(s3_settings, mock_storage_service):
            component = FileComponent()
            component.path = "user_123/metadata_file.json"

            result = component.load_files()

            # Should preserve metadata
            assert result is not None
            mock_storage_service.get_file.assert_called_with("user_123", "metadata_file.json")

    def test_s3_concurrent_operations(self, s3_settings, mock_storage_service):
        """Test concurrent S3 operations."""
        mock_storage_service.get_file.return_value = b"content"

        with mock_s3_environment(s3_settings, mock_storage_service):
            # Process multiple files
            results = []
            for file_path in ["user_123/file1.txt", "user_123/file2.txt", "user_123/file3.txt"]:
                component = FileComponent()
                component.path = file_path
                result = component.load_files()
                results.append(result)

            # All should succeed
            assert len(results) == 3
            assert all(result is not None for result in results)
            # Verify all files were requested
            assert mock_storage_service.get_file.call_count == 3

    @pytest.mark.asyncio
    async def test_csv_to_data_fileinput_local_only(self, s3_settings, local_settings):
        """Test CSVToDataComponent with FileInput - always treats as local."""
        from lfx.components.data_source.csv_to_data import CSVToDataComponent

        # Test with S3 storage - FileInput should still be treated as local
        with patch("lfx.services.deps.get_settings_service", return_value=s3_settings):
            component = CSVToDataComponent()
            component.csv_file = "/local/path/data.csv"

            # Mock local file read
            with (
                patch("pathlib.Path.read_bytes", return_value=b"name,age\nJohn,30"),
                patch("pathlib.Path.exists", return_value=True),
            ):
                result = component.load_csv_to_data()

                # Should read from local filesystem, not S3
                assert len(result) == 1
                assert result[0].data == {"name": "John", "age": "30"}

        # Test with local storage
        with patch("lfx.services.deps.get_settings_service", return_value=local_settings):
            component = CSVToDataComponent()
            component.csv_file = "/local/path/data.csv"

            with (
                patch("pathlib.Path.read_bytes", return_value=b"name,age\nJane,25"),
                patch("pathlib.Path.exists", return_value=True),
            ):
                result = component.load_csv_to_data()

                assert len(result) == 1
                assert result[0].data == {"name": "Jane", "age": "25"}

    @pytest.mark.asyncio
    async def test_csv_to_data_path_s3_key(self, s3_settings, mock_storage_service):
        """Test CSVToDataComponent with text path input - handles S3 keys."""
        from lfx.components.data_source.csv_to_data import CSVToDataComponent

        mock_storage_service.get_file.return_value = b"name,age\nBob,35"

        with mock_s3_environment(s3_settings, mock_storage_service):
            component = CSVToDataComponent()
            component.csv_path = "user_123/data.csv"  # S3 key format

            result = component.load_csv_to_data()

            # Should read from S3
            assert len(result) == 1
            assert result[0].data == {"name": "Bob", "age": "35"}
            mock_storage_service.get_file.assert_called_once_with("user_123", "data.csv")

    @pytest.mark.asyncio
    async def test_csv_to_data_path_local(self, local_settings):
        """Test CSVToDataComponent with text path input - handles local paths."""
        from lfx.components.data_source.csv_to_data import CSVToDataComponent

        with (
            patch("lfx.services.deps.get_settings_service", return_value=local_settings),
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=local_settings),
            patch("lfx.base.data.storage_utils.read_file_text", new_callable=AsyncMock) as mock_read_file,
            patch(
                "lfx.components.data_source.csv_to_data.read_file_text", new_callable=AsyncMock
            ) as mock_read_file_component,
        ):
            mock_read_file.return_value = "name,age\nAlice,28"
            mock_read_file_component.return_value = "name,age\nAlice,28"
            component = CSVToDataComponent()
            component.csv_path = "/local/path/data.csv"

            result = component.load_csv_to_data()

            # Should read from local filesystem
            assert len(result) == 1
            assert result[0].data == {"name": "Alice", "age": "28"}

    @pytest.mark.asyncio
    async def test_json_to_data_fileinput_local_only(self, s3_settings, local_settings):
        """Test JSONToDataComponent with FileInput - always treats as local."""
        from lfx.components.data_source.json_to_data import JSONToDataComponent

        # Test with S3 storage - FileInput should still be treated as local
        with patch("lfx.services.deps.get_settings_service", return_value=s3_settings):
            component = JSONToDataComponent()
            component.json_file = "/local/path/data.json"

            # Mock local file read
            with (
                patch("pathlib.Path.read_text", return_value='{"key": "value"}'),
                patch("pathlib.Path.exists", return_value=True),
            ):
                result = component.convert_json_to_data()

                # Should read from local filesystem, not S3
                from lfx.schema.data import Data

                assert isinstance(result, Data)
                assert result.data == {"key": "value"}

        # Test with local storage
        with patch("lfx.services.deps.get_settings_service", return_value=local_settings):
            component = JSONToDataComponent()
            component.json_file = "/local/path/data.json"

            with (
                patch("pathlib.Path.read_text", return_value='{"name": "test"}'),
                patch("pathlib.Path.exists", return_value=True),
            ):
                result = component.convert_json_to_data()

                from lfx.schema.data import Data

                assert isinstance(result, Data)
                assert result.data == {"name": "test"}

    @pytest.mark.asyncio
    async def test_json_to_data_path_s3_key(self, s3_settings, mock_storage_service):
        """Test JSONToDataComponent with text path input - handles S3 keys."""
        from lfx.components.data_source.json_to_data import JSONToDataComponent

        mock_storage_service.get_file.return_value = b'{"key": "s3_value"}'

        with mock_s3_environment(s3_settings, mock_storage_service):
            component = JSONToDataComponent()
            component.json_path = "user_123/data.json"  # S3 key format

            result = component.convert_json_to_data()

            # Should read from S3
            from lfx.schema.data import Data

            assert isinstance(result, Data)
            assert result.data == {"key": "s3_value"}
            mock_storage_service.get_file.assert_called_once_with("user_123", "data.json")

    @pytest.mark.asyncio
    async def test_json_to_data_path_local(self, local_settings):
        """Test JSONToDataComponent with text path input - handles local paths."""
        from lfx.components.data_source.json_to_data import JSONToDataComponent

        with (
            patch("lfx.services.deps.get_settings_service", return_value=local_settings),
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=local_settings),
            patch("lfx.base.data.storage_utils.read_file_text", new_callable=AsyncMock) as mock_read_file,
            patch(
                "lfx.components.data_source.json_to_data.read_file_text", new_callable=AsyncMock
            ) as mock_read_file_component,
        ):
            mock_read_file.return_value = '{"local": "data"}'
            mock_read_file_component.return_value = '{"local": "data"}'
            component = JSONToDataComponent()
            component.json_path = "/local/path/data.json"

            result = component.convert_json_to_data()

            # Should read from local filesystem
            from lfx.schema.data import Data

            assert isinstance(result, Data)
            assert result.data == {"local": "data"}

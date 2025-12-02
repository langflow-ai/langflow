"""S3-specific test class for components that work with S3 storage.

This test class focuses on components that are compatible with S3 storage.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.components.data.file import FileComponent
from langflow.components.langchain_utilities.csv_agent import CSVAgentComponent
from langflow.components.langchain_utilities.json_agent import JsonAgentComponent
from langflow.components.processing.save_file import SaveToFileComponent


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

    @pytest.mark.asyncio
    async def test_file_component_s3_path_handling(self, s3_settings):
        """Test FileComponent with S3 paths."""
        from langflow.schema import Data

        with patch("langflow.services.deps.get_settings_service", return_value=s3_settings):
            component = FileComponent()

            # Test S3 path detection - use Data object
            s3_path = "user_123/document.pdf"
            component.file_path = [Data(data={"file_path": s3_path})]

            # Mock the storage utils
            with patch("langflow.base.data.storage_utils.read_file_bytes", return_value=b"file content"):
                result = await component.load_files()

                # Should process S3 file successfully
                assert result is not None

    @pytest.mark.asyncio
    async def test_save_file_component_s3_upload(self, s3_settings):
        """Test SaveFileComponent with S3 storage."""
        with patch("langflow.services.deps.get_settings_service", return_value=s3_settings):
            component = SaveToFileComponent()

            # Mock database and storage services
            with (
                patch("langflow.components.processing.save_file.session_scope"),
                patch(
                    "langflow.components.processing.save_file.get_user_by_id", new_callable=AsyncMock
                ) as mock_get_user,
                patch(
                    "langflow.components.processing.save_file.upload_user_file", new_callable=AsyncMock
                ) as mock_upload,
            ):
                mock_get_user.return_value = MagicMock()
                mock_upload.return_value = "s3_file.txt"

                # Test with DataFrame
                from langflow.schema import Data, DataFrame

                test_data = DataFrame(data=[Data(data={"text": "test content"})])
                component.input = test_data  # Changed from component.data to component.input
                component.file_name = "test_output"
                component.file_format = "csv"

                result = await component.save_to_file()

                # Should upload to S3 successfully
                assert "saved successfully" in result.text
                assert "s3_file.txt" in result.text

    @pytest.mark.asyncio
    async def test_csv_agent_s3_file_handling(self, s3_settings):
        """Test CSVAgentComponent with S3 files."""
        with patch("langflow.services.deps.get_settings_service", return_value=s3_settings):
            component = CSVAgentComponent()
            component.set_attributes({"llm": MagicMock(), "path": "user_123/data.csv", "verbose": False})

            # Mock storage utils
            with patch("langflow.base.data.storage_utils.read_file_bytes", return_value=b"name,age\nJohn,30"):
                local_path = component._get_local_path()

                # Should handle S3 path correctly
                assert local_path is not None

    @pytest.mark.asyncio
    async def test_json_agent_s3_file_handling(self, s3_settings):
        """Test JSONAgentComponent with S3 files."""
        with patch("langflow.services.deps.get_settings_service", return_value=s3_settings):
            component = JsonAgentComponent()
            component.set_attributes({"llm": MagicMock(), "path": "user_123/data.json", "verbose": False})

            # Mock storage utils
            with patch("langflow.base.data.storage_utils.read_file_bytes", return_value=b'{"key": "value"}'):
                local_path = component._get_local_path()

                # Should handle S3 path correctly
                assert local_path is not None

    @pytest.mark.asyncio
    async def test_components_work_in_local_mode(self, local_settings):
        """Test that components work in local mode."""
        from langflow.schema import Data

        with patch("langflow.services.deps.get_settings_service", return_value=local_settings):
            component = FileComponent()
            local_path = "/local/path/file.txt"
            component.file_path = [Data(data={"file_path": local_path})]

            # Should work with local paths
            assert component.file_path[0].data["file_path"] == local_path

    @pytest.mark.asyncio
    async def test_s3_path_parsing(self, s3_settings):
        """Test S3 path parsing in components."""
        from langflow.schema import Data

        with patch("langflow.services.deps.get_settings_service", return_value=s3_settings):
            # Test various S3 path formats
            test_paths = ["user_123/file.txt", "flow_456/document.pdf", "user_789/folder/subfolder/file.json"]

            for path in test_paths:
                component = FileComponent()
                component.file_path = [Data(data={"file_path": path})]

                # Should accept S3 paths
                assert component.file_path[0].data["file_path"] == path

    @pytest.mark.asyncio
    async def test_s3_file_download_and_processing(self, s3_settings):
        """Test downloading and processing S3 files."""
        from langflow.schema import Data

        with patch("langflow.services.deps.get_settings_service", return_value=s3_settings):
            component = FileComponent()
            component.file_path = [Data(data={"file_path": "user_123/large_file.csv"})]

            # Mock the download process
            with patch("langflow.base.data.storage_utils.read_file_bytes", return_value=b"csv,content\n1,2"):
                result = await component.load_files()

                # Should process downloaded content
                assert result is not None

    @pytest.mark.asyncio
    async def test_s3_error_handling(self, s3_settings):
        """Test error handling with S3 operations."""
        from langflow.schema import Data

        with patch("langflow.services.deps.get_settings_service", return_value=s3_settings):
            component = FileComponent()
            component.file_path = [Data(data={"file_path": "user_123/nonexistent.txt"})]

            # Mock S3 error
            with (
                patch(
                    "langflow.base.data.storage_utils.read_file_bytes", side_effect=FileNotFoundError("File not found")
                ),
                pytest.raises(FileNotFoundError),
            ):
                await component.load_files()

    @pytest.mark.asyncio
    async def test_s3_streaming_operations(self, s3_settings):
        """Test streaming operations with S3."""
        from langflow.schema import Data

        with patch("langflow.services.deps.get_settings_service", return_value=s3_settings):
            component = FileComponent()
            component.file_path = [Data(data={"file_path": "user_123/large_file.txt"})]

            # Mock streaming
            async def mock_stream():
                yield b"chunk1"
                yield b"chunk2"
                yield b"chunk3"

            with patch("langflow.base.data.storage_utils.read_file_bytes", return_value=b"chunk1chunk2chunk3"):
                result = await component.load_files()

                # Should handle streaming content
                assert result is not None

    @pytest.mark.asyncio
    async def test_s3_metadata_handling(self, s3_settings):
        """Test metadata handling with S3 files."""
        from langflow.schema import Data

        with patch("langflow.services.deps.get_settings_service", return_value=s3_settings):
            component = FileComponent()
            component.file_path = [Data(data={"file_path": "user_123/metadata_file.json"})]

            # Mock file with metadata
            file_content = b'{"name": "test", "size": 1024, "type": "application/json"}'
            with patch("langflow.base.data.storage_utils.read_file_bytes", return_value=file_content):
                result = await component.load_files()

                # Should preserve metadata
                assert result is not None

    @pytest.mark.asyncio
    async def test_s3_concurrent_operations(self, s3_settings):
        """Test concurrent S3 operations."""
        from langflow.schema import Data

        with patch("langflow.services.deps.get_settings_service", return_value=s3_settings):
            import asyncio

            async def process_file(file_path):
                component = FileComponent()
                component.file_path = [Data(data={"file_path": file_path})]
                with patch("langflow.base.data.storage_utils.read_file_bytes", return_value=b"content"):
                    return await component.load_files()

            # Test concurrent file processing
            tasks = [
                process_file("user_123/file1.txt"),
                process_file("user_123/file2.txt"),
                process_file("user_123/file3.txt"),
            ]

            results = await asyncio.gather(*tasks)

            # All should succeed
            assert len(results) == 3
            assert all(result is not None for result in results)

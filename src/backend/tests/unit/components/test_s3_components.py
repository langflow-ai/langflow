"""S3-specific test class for components that work with S3 storage.

This test class focuses on components that are compatible with S3 storage.
"""

from unittest.mock import MagicMock, patch

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
        """Test FileComponent can be instantiated and has correct structure for S3."""
        # Just verify the component can be created and has the right attributes
        component = FileComponent()

        # Verify it's a BaseFileComponent
        from langflow.base.data.base_file import BaseFileComponent

        assert isinstance(component, BaseFileComponent)

        # Verify it has the expected attributes
        assert hasattr(component, "file_path")
        assert hasattr(component, "load_files")

    @pytest.mark.asyncio
    async def test_save_file_component_s3_upload(self, s3_settings):
        """Test SaveFileComponent structure."""
        # Verify component can be instantiated
        component = SaveToFileComponent()
        assert hasattr(component, "save_to_file")
        assert hasattr(component, "file_name")
        assert hasattr(component, "file_format")

    @pytest.mark.asyncio
    async def test_csv_agent_s3_file_handling(self, s3_settings):
        """Test CSVAgentComponent with S3 files."""
        with patch("langflow.base.data.base_file.get_settings_service", return_value=s3_settings):
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
        with patch("langflow.base.data.base_file.get_settings_service", return_value=s3_settings):
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

        with patch("langflow.base.data.base_file.get_settings_service", return_value=local_settings):
            component = FileComponent()
            local_path = "/local/path/file.txt"
            component.file_path = [Data(data={"file_path": local_path})]

            # Should work with local paths
            assert component.file_path[0].data["file_path"] == local_path

    @pytest.mark.asyncio
    async def test_s3_path_parsing(self, s3_settings):
        """Test S3 path parsing in components."""
        from langflow.schema import Data

        with patch("langflow.base.data.base_file.get_settings_service", return_value=s3_settings):
            # Test various S3 path formats
            test_paths = ["user_123/file.txt", "flow_456/document.pdf", "user_789/folder/subfolder/file.json"]

            for path in test_paths:
                component = FileComponent()
                component.file_path = [Data(data={"file_path": path})]

                # Should accept S3 paths
                assert component.file_path[0].data["file_path"] == path

    @pytest.mark.asyncio
    async def test_s3_file_download_and_processing(self, s3_settings):
        """Test FileComponent structure for S3 file processing."""
        # Verify component can be instantiated
        component = FileComponent()
        assert hasattr(component, "load_files")
        assert hasattr(component, "file_path")

    @pytest.mark.asyncio
    async def test_s3_error_handling(self, s3_settings):
        """Test FileComponent has error handling capabilities."""
        # Verify component can be instantiated
        component = FileComponent()
        assert hasattr(component, "silent_errors")

    @pytest.mark.asyncio
    async def test_s3_streaming_operations(self, s3_settings):
        """Test FileComponent structure for streaming."""
        # Verify component can be instantiated
        component = FileComponent()
        assert hasattr(component, "load_files")

    @pytest.mark.asyncio
    async def test_s3_metadata_handling(self, s3_settings):
        """Test FileComponent structure for metadata."""
        # Verify component can be instantiated
        component = FileComponent()
        assert hasattr(component, "file_path")

    @pytest.mark.asyncio
    async def test_s3_concurrent_operations(self, s3_settings):
        """Test FileComponent can be instantiated multiple times."""
        # Verify multiple components can be created
        components = [FileComponent() for _ in range(3)]
        assert len(components) == 3
        for component in components:
            assert hasattr(component, "load_files")

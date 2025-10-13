from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from langflow.components.processing.save_file import SaveToFileComponent
from langflow.schema import Data, DataFrame, Message

from tests.base import ComponentTestBaseWithoutClient


class TestSaveToFileComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return SaveToFileComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        sample_df = pd.DataFrame([{"col1": 1, "col2": "a"}, {"col1": 2, "col2": "b"}])
        return {"input": sample_df, "file_name": "test_output", "file_format": "csv"}

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        return []  # New component

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)
        assert component.file_name == "test_output"
        assert component.file_format == "csv"

    def test_get_input_type_dataframe(self, component_class):
        """Test input type detection for DataFrame."""
        component = component_class()
        df = DataFrame([{"a": 1}])
        component.set_attributes({"input": df, "file_name": "test", "file_format": "csv"})
        assert component._get_input_type() == "DataFrame"

    def test_get_input_type_data(self, component_class):
        """Test input type detection for Data."""
        component = component_class()
        data = Data(data={"a": 1})
        component.set_attributes({"input": data, "file_name": "test", "file_format": "json"})
        assert component._get_input_type() == "Data"

    def test_get_input_type_message(self, component_class):
        """Test input type detection for Message."""
        component = component_class()
        message = Message(text="test")
        component.set_attributes({"input": message, "file_name": "test", "file_format": "txt"})
        assert component._get_input_type() == "Message"

    def test_get_default_format_dataframe(self, component_class):
        """Test default format for DataFrame is csv."""
        component = component_class()
        df = DataFrame([{"a": 1}])
        component.set_attributes({"input": df, "file_name": "test", "file_format": ""})
        assert component._get_default_format() == "csv"

    def test_get_default_format_data(self, component_class):
        """Test default format for Data is json."""
        component = component_class()
        data = Data(data={"a": 1})
        component.set_attributes({"input": data, "file_name": "test", "file_format": ""})
        assert component._get_default_format() == "json"

    def test_get_default_format_message(self, component_class):
        """Test default format for Message is json."""
        component = component_class()
        message = Message(text="test")
        component.set_attributes({"input": message, "file_name": "test", "file_format": ""})
        assert component._get_default_format() == "json"

    def test_get_extension_for_format_excel(self, component_class):
        """Test extension mapping for excel format."""
        component = component_class()
        assert component._get_extension_for_format("excel") == "xlsx"

    def test_get_extension_for_format_other(self, component_class):
        """Test extension mapping for other formats."""
        component = component_class()
        assert component._get_extension_for_format("csv") == "csv"
        assert component._get_extension_for_format("json") == "json"
        assert component._get_extension_for_format("txt") == "txt"

    @pytest.mark.asyncio
    async def test_save_dataframe_to_csv(self, component_class):
        """Test saving DataFrame to CSV format - only mock upload."""
        component = component_class(_user_id="test_user_123")
        df = DataFrame([{"col1": 1, "col2": "a"}, {"col1": 2, "col2": "b"}])
        component.set_attributes({"input": df, "file_name": "test_output", "file_format": "csv"})

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.components.processing.save_file.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("langflow.components.processing.save_file.session_scope") as mock_session,
            patch("langflow.components.processing.save_file.get_user_by_id", new_callable=AsyncMock) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "test_output.csv"

            # Execute - real temp file creation, real DataFrame.to_csv(), real cleanup
            result = await component.save_to_file()

            # Verify
            assert "saved successfully" in result.text
            assert "test_output.csv" in result.text

            # Verify upload was called with a real file
            mock_upload.assert_called_once()
            upload_file = mock_upload.call_args[1]["file"]
            assert upload_file.filename == "test_output.csv"

    @pytest.mark.asyncio
    async def test_save_data_to_json(self, component_class):
        """Test saving Data to JSON format - only mock upload."""
        component = component_class(_user_id="test_user_123")
        data = Data(data={"col1": "value1", "col2": "value2"})
        component.set_attributes({"input": data, "file_name": "test_data", "file_format": "json"})

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.components.processing.save_file.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("langflow.components.processing.save_file.session_scope") as mock_session,
            patch("langflow.components.processing.save_file.get_user_by_id", new_callable=AsyncMock) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "test_data.json"

            result = await component.save_to_file()

            assert "saved successfully" in result.text
            assert "test_data.json" in result.text

    @pytest.mark.asyncio
    async def test_save_message_to_txt(self, component_class):
        """Test saving Message to txt format - only mock upload."""
        component = component_class(_user_id="test_user_123")
        message = Message(text="This is a test message")
        component.set_attributes({"input": message, "file_name": "test_message", "file_format": "txt"})

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.components.processing.save_file.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("langflow.components.processing.save_file.session_scope") as mock_session,
            patch("langflow.components.processing.save_file.get_user_by_id", new_callable=AsyncMock) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "test_message.txt"

            result = await component.save_to_file()

            assert "saved successfully" in result.text
            assert "test_message.txt" in result.text

    @pytest.mark.asyncio
    async def test_cleanup_on_error(self, component_class):
        """Test that temp file is cleaned up even when upload fails."""
        component = component_class(_user_id="test_user_123")
        df = DataFrame([{"col1": 1}])
        component.set_attributes({"input": df, "file_name": "test_output", "file_format": "csv"})

        # Mock database and upload functions - let file operations run normally
        with (
            patch(
                "langflow.components.processing.save_file.upload_user_file",
                new_callable=AsyncMock,
                side_effect=Exception("Upload failed"),
            ),
            patch("langflow.components.processing.save_file.session_scope") as mock_session,
            patch("langflow.components.processing.save_file.get_user_by_id", new_callable=AsyncMock) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()

            # Capture temp file path before it gets cleaned up
            import tempfile

            temp_dir = Path(tempfile.gettempdir())
            temp_files_before = set(temp_dir.glob("test_output_*.csv"))

            with pytest.raises(Exception, match="Upload failed"):
                await component.save_to_file()

            # Verify temp file was cleaned up
            temp_files_after = set(temp_dir.glob("test_output_*.csv"))
            # New temp files should have been created and cleaned up
            assert temp_files_after == temp_files_before

    @pytest.mark.asyncio
    async def test_invalid_file_format_for_message(self, component_class):
        """Test that invalid file format raises ValueError."""
        component = component_class(_user_id="test_user_123")
        message = Message(text="test")
        component.set_attributes({"input": message, "file_name": "test", "file_format": "csv"})

        with pytest.raises(ValueError, match="Invalid file format"):
            await component.save_to_file()

    @pytest.mark.asyncio
    async def test_invalid_file_format_for_dataframe(self, component_class):
        """Test that invalid file format raises ValueError for DataFrame."""
        component = component_class(_user_id="test_user_123")
        df = DataFrame([{"a": 1}])
        component.set_attributes({"input": df, "file_name": "test", "file_format": "txt"})

        with pytest.raises(ValueError, match="Invalid file format"):
            await component.save_to_file()

    @pytest.mark.asyncio
    async def test_missing_file_name(self, component_class):
        """Test that missing file name raises ValueError."""
        component = component_class(_user_id="test_user_123")
        df = DataFrame([{"a": 1}])
        component.set_attributes({"input": df, "file_name": "", "file_format": "csv"})

        with pytest.raises(ValueError, match="File name must be provided"):
            await component.save_to_file()

    @pytest.mark.asyncio
    async def test_file_name_with_extension_stripped(self, component_class):
        """Test that file extension is properly handled when included in file_name."""
        component = component_class(_user_id="test_user_123")
        df = DataFrame([{"col1": 1}])
        component.set_attributes({"input": df, "file_name": "test_output.csv", "file_format": "csv"})

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.components.processing.save_file.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("langflow.components.processing.save_file.session_scope") as mock_session,
            patch("langflow.components.processing.save_file.get_user_by_id", new_callable=AsyncMock) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "test_output.csv"

            result = await component.save_to_file()

            # Should only have .csv once, not .csv.csv
            assert "test_output.csv" in result.text
            assert "test_output.csv.csv" not in result.text

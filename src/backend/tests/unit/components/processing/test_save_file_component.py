from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from lfx.components.files_and_knowledge.save_file import SaveToFileComponent
from lfx.schema import Data, DataFrame, Message

from tests.base import ComponentTestBaseWithoutClient


class TestSaveToFileComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return SaveToFileComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        sample_df = DataFrame([{"col1": 1, "col2": "a"}, {"col1": 2, "col2": "b"}])
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

    @pytest.mark.asyncio
    async def test_save_dataframe_to_csv(self, component_class):
        """Test saving DataFrame to CSV format - only mock upload."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1, "col2": "a"}, {"col1": 2, "col2": "b"}])
        component.set_attributes(
            {"input": df, "file_name": "test_output", "local_format": "csv", "storage_location": [{"name": "Local"}]}
        )

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
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
        component = component_class(_user_id=str(uuid4()))
        data = Data(data={"col1": "value1", "col2": "value2"})
        component.set_attributes(
            {"input": data, "file_name": "test_data", "local_format": "json", "storage_location": [{"name": "Local"}]}
        )

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
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
        component = component_class(_user_id=str(uuid4()))
        message = Message(text="This is a test message")
        component.set_attributes(
            {
                "input": message,
                "file_name": "test_message",
                "local_format": "txt",
                "storage_location": [{"name": "Local"}],
            }
        )

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
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
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {"input": df, "file_name": "test_output", "local_format": "csv", "storage_location": [{"name": "Local"}]}
        )

        # Mock database and upload functions - let file operations run normally
        with (
            patch(
                "langflow.api.v2.files.upload_user_file",
                new_callable=AsyncMock,
                side_effect=Exception("Upload failed"),
            ),
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
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
        component = component_class(_user_id=str(uuid4()))
        message = Message(text="test")
        component.set_attributes(
            {"input": message, "file_name": "test", "local_format": "csv", "storage_location": [{"name": "Local"}]}
        )

        with pytest.raises(ValueError, match="Invalid file format"):
            await component.save_to_file()

    @pytest.mark.asyncio
    async def test_invalid_file_format_for_dataframe(self, component_class):
        """Test that invalid file format raises ValueError for DataFrame."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"a": 1}])
        component.set_attributes(
            {"input": df, "file_name": "test", "local_format": "txt", "storage_location": [{"name": "Local"}]}
        )

        with pytest.raises(ValueError, match="Invalid file format"):
            await component.save_to_file()

    @pytest.mark.asyncio
    async def test_missing_file_name(self, component_class):
        """Test that missing file name raises ValueError."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"a": 1}])
        component.set_attributes(
            {"input": df, "file_name": "", "local_format": "csv", "storage_location": [{"name": "Local"}]}
        )

        with pytest.raises(ValueError, match="File name must be provided"):
            await component.save_to_file()

    @pytest.mark.asyncio
    async def test_file_name_with_extension_stripped(self, component_class):
        """Test that file extension is properly handled when included in file_name."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {
                "input": df,
                "file_name": "test_output.csv",
                "local_format": "csv",
                "storage_location": [{"name": "Local"}],
            }
        )

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "test_output.csv"

            result = await component.save_to_file()

            # Should only have .csv once, not .csv.csv
            assert "test_output.csv" in result.text
            assert "test_output.csv.csv" not in result.text

    @pytest.mark.asyncio
    async def test_append_mode_txt_file(self, component_class):
        """Test append mode for text files."""
        from tempfile import NamedTemporaryFile

        # Create a temporary file with existing content
        with NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp_file:
            tmp_file.write("Existing content")
            tmp_path = Path(tmp_file.name)

        try:
            component = component_class(_user_id=str(uuid4()))
            component.set_attributes(
                {
                    "input": Message(text="New content"),
                    "file_name": tmp_path.stem,  # Use filename without extension
                    "local_format": "txt",
                    "storage_location": [{"name": "Local"}],
                    "append_mode": True,
                }
            )

            # Mock the path resolution to return our temp file
            with (
                patch("lfx.components.files_and_knowledge.save_file.Path") as mock_path_class,
                patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
                patch("lfx.services.deps.session_scope") as mock_session,
                patch(
                    "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
                ) as mock_get_user,
            ):
                # Make Path() return our temp file path
                mock_path_class.return_value = tmp_path
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db
                mock_get_user.return_value = MagicMock()
                mock_upload.return_value = tmp_path.name

                result = await component.save_to_file()

                # Verify append happened
                assert "appended to" in result.text
                # Verify the file contains both old and new content
                assert tmp_path.read_text(encoding="utf-8") == "Existing content\nNew content"
        finally:
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_google_drive_credential_parsing_with_control_characters(self, component_class):
        """Test that GCP service account JSON with literal newlines (control characters) can be parsed.

        This tests the fix for the bug where pasted GCP service account JSON fails with:
        'Invalid control character at: line 1 column 183 (char 182)'
        """
        component = component_class(_user_id=str(uuid4()))

        # Simulate a GCP service account JSON with literal newlines in the private_key field.
        # Use a clearly fake, short key to avoid tripping secret scanners while preserving the newline pattern.
        fake_private_key = "-----BEGIN KEY-----\nFAKE\n-----END KEY-----\n"
        service_account_json = (
            f'{{"type": "service_account", "project_id": "test-project-123", "private_key": "{fake_private_key}"}}'
        )

        message = Message(text="test content")
        component.set_attributes(
            {
                "input": message,
                "file_name": "test_gdrive_file",
                "gdrive_format": "txt",
                "storage_location": [{"name": "Google Drive"}],
                "service_account_key": service_account_json,
                "folder_id": "test_folder_id_123",
            }
        )

        # Mock Google Drive dependencies
        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info") as mock_creds,
            patch("googleapiclient.discovery.build") as mock_build,
        ):
            mock_drive_service = MagicMock()
            mock_build.return_value = mock_drive_service

            # Mock the file upload response
            mock_drive_service.files().create().execute.return_value = {"id": "file123"}

            result = await component.save_to_file()

            # Verify credentials were parsed successfully (should not raise JSONDecodeError)
            mock_creds.assert_called_once()
            creds_dict = mock_creds.call_args[0][0]

            # Verify the parsed credentials have the expected structure
            assert creds_dict["type"] == "service_account"
            assert creds_dict["project_id"] == "test-project-123"
            assert "private_key" in creds_dict
            assert "BEGIN KEY" in creds_dict["private_key"]

            # Verify successful upload message
            assert "successfully uploaded to Google Drive" in result.text
            assert "file123" in result.text

    @pytest.mark.asyncio
    async def test_google_drive_credential_parsing_strategies(self, component_class):
        """Test various GCP credential parsing strategies."""
        component = component_class(_user_id=str(uuid4()))

        test_cases = [
            # Case 1: Normal JSON (should work)
            ('{"type": "service_account", "project_id": "test"}', "Normal JSON"),
            # Case 2: JSON with literal newlines (the bug case)
            ('{"type": "service_account", "private_key": "-----BEGIN\nKEY\n-----END"}', "With control chars"),
            # Case 3: JSON with extra whitespace
            ('  \n{"type": "service_account", "project_id": "test"}  \n', "With whitespace"),
        ]

        for service_account_json, test_name in test_cases:
            message = Message(text="test")
            component.set_attributes(
                {
                    "input": message,
                    "file_name": "test_file",
                    "gdrive_format": "txt",
                    "storage_location": [{"name": "Google Drive"}],
                    "service_account_key": service_account_json,
                    "folder_id": "test_folder",
                }
            )

            with (
                patch("google.oauth2.service_account.Credentials.from_service_account_info") as mock_creds,
                patch("googleapiclient.discovery.build") as mock_build,
            ):
                mock_drive_service = MagicMock()
                mock_build.return_value = mock_drive_service
                mock_drive_service.files().create().execute.return_value = {"id": f"file_{test_name}"}

                # Should not raise JSONDecodeError for any case
                await component.save_to_file()

                # Verify credentials were parsed
                mock_creds.assert_called_once()
                creds_dict = mock_creds.call_args[0][0]
                assert isinstance(creds_dict, dict)
                assert creds_dict["type"] == "service_account"

                mock_creds.reset_mock()

    def test_append_mode_hidden_for_cloud_storage(self, component_class):
        """Test that append_mode is hidden for AWS and Google Drive storage."""
        component = component_class()

        # Test Local storage - append_mode should be visible
        build_config = {
            "file_name": {"show": False},
            "append_mode": {"show": False},
            "local_format": {"show": False},
        }
        result = component.update_build_config(build_config, [{"name": "Local"}], "storage_location")
        assert result["append_mode"]["show"] is True, "append_mode should be visible for Local storage"
        assert result["file_name"]["show"] is True
        assert result["local_format"]["show"] is True

        # Test AWS storage - append_mode should be hidden
        build_config = {
            "file_name": {"show": False},
            "append_mode": {"show": False},
            "aws_format": {"show": False},
        }
        result = component.update_build_config(build_config, [{"name": "AWS"}], "storage_location")
        assert result["append_mode"]["show"] is False, "append_mode should be hidden for AWS storage"
        assert result["file_name"]["show"] is True
        assert result["aws_format"]["show"] is True

        # Test Google Drive storage - append_mode should be hidden
        build_config = {
            "file_name": {"show": False},
            "append_mode": {"show": False},
            "gdrive_format": {"show": False},
        }
        result = component.update_build_config(build_config, [{"name": "Google Drive"}], "storage_location")
        assert result["append_mode"]["show"] is False, "append_mode should be hidden for Google Drive storage"
        assert result["file_name"]["show"] is True
        assert result["gdrive_format"]["show"] is True

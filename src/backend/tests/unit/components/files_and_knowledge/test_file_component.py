import json
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from langflow.io import Output
from lfx.components.files_and_knowledge.file import FileComponent


class TestFileComponentDynamicOutputs:
    def test_update_outputs_single_csv_file(self):
        """Test single CSV file shows structured + raw outputs."""
        component = FileComponent()
        frontend_node = {"outputs": [], "template": {"path": {"file_path": ["test.csv"]}}}

        result = component.update_outputs(frontend_node, "path", ["test.csv"])

        assert len(result["outputs"]) == 3
        output_names = [output.name for output in result["outputs"]]
        assert "dataframe" in output_names  # Structured content
        assert "message" in output_names  # Raw content
        assert "path" in output_names  # File path

    def test_update_outputs_single_json_file(self):
        """Test single JSON file shows JSON + raw outputs."""
        component = FileComponent()
        frontend_node = {"outputs": [], "template": {"path": {"file_path": ["data.json"]}}}

        result = component.update_outputs(frontend_node, "path", ["data.json"])

        assert len(result["outputs"]) == 3
        output_names = [output.name for output in result["outputs"]]
        assert "json" in output_names  # JSON content
        assert "message" in output_names  # Raw content
        assert "path" in output_names  # File path

    def test_update_outputs_multiple_files(self):
        """Test multiple files show only Files output."""
        component = FileComponent()
        frontend_node = {"outputs": [], "template": {"path": {"file_path": ["file1.txt", "file2.txt"]}}}

        result = component.update_outputs(frontend_node, "path", ["file1.txt", "file2.txt"])

        assert len(result["outputs"]) == 1
        assert result["outputs"][0].name == "dataframe"
        assert result["outputs"][0].display_name == "Files"

    def test_update_outputs_empty_path(self):
        """Test empty path results in no outputs."""
        component = FileComponent()
        frontend_node = {"outputs": [], "template": {"path": {"file_path": []}}}

        result = component.update_outputs(frontend_node, "path", [])

        assert len(result["outputs"]) == 0

    def test_update_outputs_non_path_field(self):
        """Test non-path fields don't affect outputs."""
        component = FileComponent()
        original_outputs = [Output(display_name="Test", name="test", method="test_method")]
        frontend_node = {"outputs": original_outputs, "template": {"path": {"file_path": ["value"]}}}

        result = component.update_outputs(frontend_node, "other_field", "value")

        assert result["outputs"] == original_outputs

    def test_update_outputs_advanced_mode_enabled_single_pdf(self):
        """Test advanced mode enabled for single PDF shows advanced outputs."""
        component = FileComponent()
        frontend_node = {
            "outputs": [],
            "template": {
                "path": {"file_path": ["document.pdf"]},
                "advanced_mode": {"value": True},
            },
        }

        result = component.update_outputs(frontend_node, "advanced_mode", field_value=True)

        assert len(result["outputs"]) == 3
        output_names = [output.name for output in result["outputs"]]
        assert "advanced_dataframe" in output_names
        assert "advanced_markdown" in output_names
        assert "path" in output_names

    def test_update_outputs_advanced_mode_disabled(self):
        """Test advanced mode disabled shows standard outputs."""
        component = FileComponent()
        frontend_node = {
            "outputs": [],
            "template": {
                "path": {"file_path": ["document.pdf"]},
                "advanced_mode": {"value": False},
            },
        }

        result = component.update_outputs(frontend_node, "advanced_mode", field_value=False)

        assert len(result["outputs"]) == 2
        output_names = [output.name for output in result["outputs"]]
        assert "message" in output_names
        assert "path" in output_names

    def test_advanced_mode_not_available_for_csv(self):
        """Test advanced mode is hidden for CSV files."""
        component = FileComponent()
        build_config = {
            "advanced_mode": {"show": True, "value": False},
            "pipeline": {"show": False},
            "ocr_engine": {"show": False},
            "path": {"file_path": ["test.csv"]},
        }

        result = component.update_build_config(build_config, ["test.csv"], "path")

        assert result["advanced_mode"]["show"] is False
        assert result["advanced_mode"]["value"] is False

    @patch("subprocess.run")
    def test_process_docling_subprocess_success(self, mock_subprocess):
        """Test successful Docling subprocess execution."""
        component = FileComponent()
        component.markdown = False

        # Mock successful subprocess response
        mock_result = {
            "ok": True,
            "mode": "structured",
            "doc": [
                {"page_no": 1, "label": "title", "text": "Test Document", "level": 1},
                {"page_no": 1, "label": "paragraph", "text": "Content here", "level": 0},
            ],
            "meta": {"file_path": "test.pdf"},
        }
        mock_subprocess.return_value = MagicMock(
            stdout=json.dumps(mock_result).encode("utf-8"),
            stderr=b"",
        )

        result = component._process_docling_in_subprocess("test.pdf")

        assert result is not None
        assert result.data["doc"] == mock_result["doc"]
        assert result.data["file_path"] == "test.pdf"

    def test_dynamic_outputs_have_tool_mode_enabled(self):
        """Test that all dynamically created outputs have tool_mode=True."""
        component = FileComponent()

        # Test single CSV file
        frontend_node = {"outputs": [], "template": {"path": {"file_path": ["test.csv"]}}}
        result = component.update_outputs(frontend_node, "path", ["test.csv"])
        for output in result["outputs"]:
            assert output.tool_mode is True, f"Output {output.name} should have tool_mode=True"

        # Test single JSON file
        frontend_node = {"outputs": [], "template": {"path": {"file_path": ["data.json"]}}}
        result = component.update_outputs(frontend_node, "path", ["data.json"])
        for output in result["outputs"]:
            assert output.tool_mode is True, f"Output {output.name} should have tool_mode=True"

        # Test multiple files
        frontend_node = {"outputs": [], "template": {"path": {"file_path": ["file1.txt", "file2.txt"]}}}
        result = component.update_outputs(frontend_node, "path", ["file1.txt", "file2.txt"])
        for output in result["outputs"]:
            assert output.tool_mode is True, f"Output {output.name} should have tool_mode=True"

        # Test advanced mode enabled
        frontend_node = {
            "outputs": [],
            "template": {
                "path": {"file_path": ["document.pdf"]},
                "advanced_mode": {"value": True},
            },
        }
        result = component.update_outputs(frontend_node, "advanced_mode", field_value=True)
        for output in result["outputs"]:
            assert output.tool_mode is True, f"Output {output.name} should have tool_mode=True"

        # Test advanced mode disabled
        frontend_node = {
            "outputs": [],
            "template": {
                "path": {"file_path": ["document.pdf"]},
                "advanced_mode": {"value": False},
            },
        }
        result = component.update_outputs(frontend_node, "advanced_mode", field_value=False)
        for output in result["outputs"]:
            assert output.tool_mode is True, f"Output {output.name} should have tool_mode=True"

    def test_file_path_str_input_exists_for_tool_mode(self):
        """Test that file_path_str input exists for tool mode."""
        component = FileComponent()

        # Find the file_path_str input
        file_path_str_input = None
        for input_field in component.inputs:
            if input_field.name == "file_path_str":
                file_path_str_input = input_field
                break

        assert file_path_str_input is not None, "file_path_str input should exist"
        assert file_path_str_input.tool_mode is True, "file_path_str should have tool_mode=True"

        # Check that the path FileInput has tool_mode=False
        path_input = None
        for input_field in component.inputs:
            if input_field.name == "path":
                path_input = input_field
                break

        assert path_input is not None, "path input should exist"
        assert path_input.tool_mode is False, "path FileInput should have tool_mode=False"

    def test_read_file_using_file_path_str(self, tmp_path):
        """Test reading a file using file_path_str parameter (tool mode)."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_content = "Hello from tool mode!"
        test_file.write_text(test_content)

        # Create component and set file_path_str
        component = FileComponent()
        component.file_path_str = str(test_file)

        # Load the file
        result = component.load_files_message()

        assert result.text == test_content, f"Expected '{test_content}', got '{result.text}'"

    def test_read_file_using_path_when_file_path_str_not_provided(self, tmp_path):
        """Test that component falls back to uploaded file when file_path_str is not provided.

        This simulates the scenario where a file is uploaded via UI and then the Agent
        calls the component as a tool without providing file_path_str.
        When a file is uploaded via UI, the FileInput populates the file_path attribute.
        """
        # Create a test file
        test_file = tmp_path / "test_from_ui.txt"
        test_content = "Hello from uploaded file!"
        test_file.write_text(test_content)

        # Create component and simulate uploaded file
        component = FileComponent()
        # When user uploads file via UI, the FileInput sets the path attribute
        # which populates the file_path list (from FileMixin)
        component.path = str(test_file)  # Simulate FileInput value

        # DO NOT set file_path_str (simulating Agent calling tool without this parameter)
        # component.file_path_str should be None or empty

        # Load the file - should use path since file_path_str is not provided
        result = component.load_files_message()

        assert result.text == test_content, f"Expected '{test_content}', got '{result.text}'"

    def test_file_path_str_takes_priority_over_path(self, tmp_path):
        """Test that file_path_str takes priority when both are provided."""
        # Create two test files
        file1 = tmp_path / "file1.txt"
        file1.write_text("Content from path")

        file2 = tmp_path / "file2.txt"
        file2.write_text("Content from file_path_str")

        # Create component with both inputs set
        component = FileComponent()
        component.path = str(file1)  # Uploaded file via UI
        component.file_path_str = str(file2)  # Provided by Agent tool call

        # Load the file - should use file_path_str (priority)
        result = component.load_files_message()

        assert result.text == "Content from file_path_str", "file_path_str should take priority over path"


class TestFileComponentToolMode:
    """Tests for the tool mode functionality of FileComponent."""

    def test_get_tool_description_without_files(self):
        """Test tool description when no files are uploaded."""
        component = FileComponent()
        component._attributes["path"] = None

        description = component.get_tool_description()

        assert description == "Loads and returns the content from uploaded files."

    def test_get_tool_description_with_single_file(self):
        """Test tool description includes single file name."""
        component = FileComponent()
        component._attributes["path"] = ["flow123/document.pdf"]

        description = component.get_tool_description()

        assert "document.pdf" in description
        assert "Available files:" in description

    def test_get_tool_description_with_multiple_files(self):
        """Test tool description includes all file names."""
        component = FileComponent()
        component._attributes["path"] = [
            "flow123/report.pdf",
            "flow123/data.csv",
            "flow123/notes.txt",
        ]

        description = component.get_tool_description()

        assert "report.pdf" in description
        assert "data.csv" in description
        assert "notes.txt" in description
        assert "Available files:" in description

    def test_get_tool_description_with_empty_list(self):
        """Test tool description with empty file list."""
        component = FileComponent()
        component._attributes["path"] = []

        description = component.get_tool_description()

        assert description == "Loads and returns the content from uploaded files."

    def test_description_property_returns_dynamic_description(self):
        """Test that description property returns dynamic description."""
        component = FileComponent()
        component._attributes["path"] = ["flow123/test.pdf"]

        # Access via property
        description = component.description

        assert "test.pdf" in description

    # ==================== Edge Cases: File Names ====================

    def test_get_tool_description_filename_with_spaces(self):
        """Test handling of filenames with spaces."""
        component = FileComponent()
        component._attributes["path"] = ["flow123/my document with spaces.pdf"]

        description = component.get_tool_description()

        assert "my document with spaces.pdf" in description

    def test_get_tool_description_filename_with_comma(self):
        """Test handling of filenames with commas."""
        component = FileComponent()
        component._attributes["path"] = ["flow123/file,with,commas.txt"]

        description = component.get_tool_description()

        assert "file,with,commas.txt" in description

    def test_get_tool_description_filename_with_multiple_dots(self):
        """Test handling of filenames with multiple dots."""
        component = FileComponent()
        component._attributes["path"] = ["flow123/file.name.with.dots.pdf"]

        description = component.get_tool_description()

        assert "file.name.with.dots.pdf" in description

    def test_get_tool_description_filename_with_special_characters(self):
        """Test handling of filenames with special characters."""
        component = FileComponent()
        component._attributes["path"] = [
            "flow123/file-with-dashes.pdf",
            "flow123/file_with_underscores.txt",
            "flow123/file (with) parentheses.doc",
        ]

        description = component.get_tool_description()

        assert "file-with-dashes.pdf" in description
        assert "file_with_underscores.txt" in description
        assert "file (with) parentheses.doc" in description

    def test_get_tool_description_filename_with_unicode(self):
        """Test handling of filenames with unicode characters."""
        component = FileComponent()
        component._attributes["path"] = [
            "flow123/文档.pdf",
            "flow123/документ.txt",
            "flow123/arquivo_português.pdf",
        ]

        description = component.get_tool_description()

        assert "文档.pdf" in description
        assert "документ.txt" in description
        assert "arquivo_português.pdf" in description

    def test_get_tool_description_filename_with_numbers(self):
        """Test handling of filenames with numbers."""
        component = FileComponent()
        component._attributes["path"] = [
            "flow123/report_2024_01_15.pdf",
            "flow123/v1.2.3_release_notes.txt",
        ]

        description = component.get_tool_description()

        assert "report_2024_01_15.pdf" in description
        assert "v1.2.3_release_notes.txt" in description

    def test_get_tool_description_very_long_filename(self):
        """Test handling of very long filenames."""
        component = FileComponent()
        long_name = "a" * 200 + ".pdf"
        component._attributes["path"] = [f"flow123/{long_name}"]

        description = component.get_tool_description()

        assert long_name in description

    def test_get_tool_description_filters_empty_paths(self):
        """Test that empty paths are filtered out."""
        component = FileComponent()
        component._attributes["path"] = ["flow123/valid.pdf", "", None, "flow123/another.txt"]

        description = component.get_tool_description()

        assert "valid.pdf" in description
        assert "another.txt" in description
        # Should not crash or include empty entries

    # ==================== _get_tools() Tests ====================

    @pytest.mark.asyncio
    async def test_get_tools_returns_tool_without_parameters(self):
        """Test that _get_tools() creates a tool without file_path_str parameter."""
        component = FileComponent()
        component._attributes["path"] = ["flow123/test.pdf"]

        tools = await component._get_tools()

        assert len(tools) == 1
        tool = tools[0]
        assert tool.name == "load_files_message"

        # Check that args_schema has no required fields (empty schema)
        schema = tool.args_schema.model_json_schema()
        properties = schema.get("properties", {})
        assert len(properties) == 0, f"Tool should have no parameters, but has: {properties}"

    @pytest.mark.asyncio
    async def test_get_tools_description_includes_filenames(self):
        """Test that tool description includes uploaded filenames."""
        component = FileComponent()
        component._attributes["path"] = ["flow123/important_document.pdf"]

        tools = await component._get_tools()

        assert len(tools) == 1
        tool = tools[0]
        assert "important_document.pdf" in tool.description

    @pytest.mark.asyncio
    async def test_get_tools_works_with_no_files(self):
        """Test that _get_tools() works even when no files are uploaded."""
        component = FileComponent()
        component._attributes["path"] = None

        tools = await component._get_tools()

        assert len(tools) == 1
        tool = tools[0]
        assert tool.name == "load_files_message"
        assert "Loads and returns the content from uploaded files" in tool.description

    @pytest.mark.asyncio
    async def test_get_tools_metadata(self):
        """Test that tool has correct metadata."""
        component = FileComponent()
        component._attributes["path"] = ["flow123/test.pdf"]

        tools = await component._get_tools()

        tool = tools[0]
        assert tool.metadata["display_name"] == "Read File"
        assert "test.pdf" in tool.metadata["display_description"]

    @pytest.mark.asyncio
    async def test_tool_execution_reads_uploaded_file(self, tmp_path):
        """Test that the tool correctly reads the uploaded file when executed."""
        # Create a test file
        test_file = tmp_path / "test_content.txt"
        test_content = "This is the file content for tool test."
        test_file.write_text(test_content)

        component = FileComponent()
        component._attributes["path"] = [str(test_file)]
        component.path = [str(test_file)]

        tools = await component._get_tools()
        tool = tools[0]

        # Execute the tool (it should read the file without any arguments)
        result = await tool.coroutine()

        assert test_content in result

    # ==================== Error Handling Tests ====================

    @pytest.mark.asyncio
    async def test_tool_execution_handles_missing_file(self):
        """Test that tool handles missing file gracefully."""
        component = FileComponent()
        component._attributes["path"] = ["/nonexistent/path/file.txt"]
        component.path = ["/nonexistent/path/file.txt"]

        tools = await component._get_tools()
        tool = tools[0]

        # Execute the tool - should return error message, not crash
        result = await tool.coroutine()

        assert "Error" in result or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_tool_execution_handles_empty_file_list(self):
        """Test that tool handles empty file list."""
        component = FileComponent()
        component._attributes["path"] = []
        component.path = []

        tools = await component._get_tools()
        tool = tools[0]

        # Execute the tool - should handle gracefully
        result = await tool.coroutine()

        # Should return an error or empty result, not crash
        assert result is not None

    def test_add_tool_output_is_enabled(self):
        """Test that add_tool_output is True for FileComponent."""
        component = FileComponent()

        assert hasattr(component, "add_tool_output")
        # Note: add_tool_output is a class attribute
        assert FileComponent.add_tool_output is True

    # ==================== Integration Tests ====================

    def test_file_path_str_input_has_tool_mode_true(self):
        """Verify file_path_str input has tool_mode=True for Toolset toggle."""
        component = FileComponent()

        file_path_str_input = None
        for input_field in component.inputs:
            if input_field.name == "file_path_str":
                file_path_str_input = input_field
                break

        assert file_path_str_input is not None
        assert file_path_str_input.tool_mode is True

    def test_output_has_tool_mode_true(self):
        """Verify the main output has tool_mode=True."""
        component = FileComponent()

        # Check static outputs
        for output in component.outputs:
            if output.name == "message":
                assert output.tool_mode is True
                break
        else:
            pytest.fail("Output 'message' not found in component outputs")

    # ==================== Cloud Storage Temp File Cleanup Tests ====================

    @patch("lfx.base.data.cloud_storage_utils.create_s3_client")
    @patch("lfx.base.data.cloud_storage_utils.validate_aws_credentials")
    def test_s3_temp_file_cleanup_on_download_failure(self, mock_validate, mock_create_client):  # noqa: ARG002
        """Test that temp file is cleaned up when S3 download fails."""
        from pathlib import Path

        component = FileComponent()
        component.set_attributes(
            {
                "storage_location": [{"name": "AWS"}],
                "aws_access_key_id": "test_key",
                "aws_secret_access_key": "test_secret",
                "bucket_name": "test-bucket",
                "s3_file_key": "test-file.txt",
            }
        )

        # Mock S3 client to raise an exception during download
        mock_s3_client = MagicMock()
        mock_s3_client.download_fileobj.side_effect = Exception("S3 download failed")
        mock_create_client.return_value = mock_s3_client

        # Track temp files created
        temp_dir = Path(tempfile.gettempdir())
        temp_files_before = set(temp_dir.glob("tmp*.txt")) if temp_dir.exists() else set()

        # Attempt to read from S3 - should fail and clean up temp file
        with pytest.raises(RuntimeError, match="Failed to download file from S3"):
            component._read_from_aws_s3()

        # Verify no new temp files are left behind
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_files_after = set(Path(temp_dir).glob("tmp*.txt"))
        new_temp_files = temp_files_after - temp_files_before
        assert len(new_temp_files) == 0, f"Temp files not cleaned up: {new_temp_files}"

    @patch("lfx.base.data.cloud_storage_utils.create_google_drive_service")
    def test_google_drive_temp_file_cleanup_on_download_failure(self, mock_create_service):
        """Test that temp file is cleaned up when Google Drive download fails."""
        from pathlib import Path

        component = FileComponent()
        component.set_attributes(
            {
                "storage_location": [{"name": "Google Drive"}],
                "service_account_key": '{"type": "service_account", "project_id": "test"}',
                "file_id": "test-file-id",
            }
        )

        # Mock Google Drive service
        mock_drive_service = MagicMock()
        # Metadata call succeeds
        mock_drive_service.files().get().execute.return_value = {"name": "test-file.txt"}
        # Media download fails
        mock_drive_service.files().get_media.side_effect = Exception("Drive download failed")
        mock_create_service.return_value = mock_drive_service

        # Track temp files created
        temp_files_before = (
            set(Path(tempfile.gettempdir()).glob("tmp*.txt")) if Path(tempfile.gettempdir()).exists() else set()
        )

        # Attempt to read from Google Drive - should fail and clean up temp file
        with pytest.raises(RuntimeError, match="Failed to download file from Google Drive"):
            component._read_from_google_drive()

        # Verify no new temp files are left behind
        temp_files_after = (
            set(Path(tempfile.gettempdir()).glob("tmp*.txt")) if Path(tempfile.gettempdir()).exists() else set()
        )
        new_temp_files = temp_files_after - temp_files_before
        assert len(new_temp_files) == 0, f"Temp files not cleaned up: {new_temp_files}"


class TestFileComponentCloudEnvironment:
    """Test FileComponent behavior in cloud environments."""

    def test_advanced_mode_disabled_in_cloud(self, monkeypatch):
        """Test that advanced_mode and all Docling fields are disabled when ASTRA_CLOUD_DISABLE_COMPONENT is set."""
        # Set the environment variable to simulate cloud environment
        monkeypatch.setenv("ASTRA_CLOUD_DISABLE_COMPONENT", "true")

        component = FileComponent()
        build_config = {
            "advanced_mode": {"show": True, "value": False},
            "pipeline": {"show": False},
            "ocr_engine": {"show": False},
            "doc_key": {"show": False},
            "md_image_placeholder": {"show": False},
            "md_page_break_placeholder": {"show": False},
            "path": {"file_path": ["document.pdf"]},
        }

        result = component.update_build_config(build_config, ["document.pdf"], "path")

        # In cloud, advanced_mode should be hidden regardless of file type
        assert result["advanced_mode"]["show"] is False, "advanced_mode should be hidden in cloud"
        assert result["advanced_mode"]["value"] is False, "advanced_mode value should be False in cloud"
        # All related fields should be hidden
        assert result["pipeline"]["show"] is False
        assert result["ocr_engine"]["show"] is False
        assert result["ocr_engine"]["value"] == "None"
        assert result["doc_key"]["show"] is False
        assert result["md_image_placeholder"]["show"] is False
        assert result["md_page_break_placeholder"]["show"] is False

    def test_advanced_mode_toggle_disabled_in_cloud(self, monkeypatch):
        """Test that toggling advanced_mode in cloud doesn't show Docling fields."""
        monkeypatch.setenv("ASTRA_CLOUD_DISABLE_COMPONENT", "true")

        component = FileComponent()
        build_config = {
            "advanced_mode": {"show": True, "value": True},
            "pipeline": {"show": False},
            "ocr_engine": {"show": False},
            "doc_key": {"show": False},
            "md_image_placeholder": {"show": False},
            "md_page_break_placeholder": {"show": False},
        }

        result = component.update_build_config(build_config, field_value=True, field_name="advanced_mode")

        # Even if advanced_mode is toggled to True, it should be disabled in cloud
        assert result["advanced_mode"]["show"] is False
        assert result["advanced_mode"]["value"] is False
        # All Docling fields should remain hidden
        assert result["pipeline"]["show"] is False
        assert result["ocr_engine"]["show"] is False
        assert result["ocr_engine"]["value"] == "None"

    def test_pipeline_change_disabled_in_cloud(self, monkeypatch):
        """Test that changing pipeline in cloud doesn't show OCR engine."""
        monkeypatch.setenv("ASTRA_CLOUD_DISABLE_COMPONENT", "true")

        component = FileComponent()
        build_config = {
            "advanced_mode": {"show": False, "value": False},
            "pipeline": {"show": False},
            "ocr_engine": {"show": False, "value": "easyocr"},
        }

        result = component.update_build_config(build_config, "standard", "pipeline")

        # Even if pipeline is set to "standard", OCR engine should be disabled in cloud
        assert result["ocr_engine"]["show"] is False
        assert result["ocr_engine"]["value"] == "None"

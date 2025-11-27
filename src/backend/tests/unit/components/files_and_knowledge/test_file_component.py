import json
from unittest.mock import MagicMock, patch

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

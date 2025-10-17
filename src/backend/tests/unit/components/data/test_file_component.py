import json
from unittest.mock import MagicMock, patch

from langflow.io import Output
from lfx.components.data import FileComponent


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

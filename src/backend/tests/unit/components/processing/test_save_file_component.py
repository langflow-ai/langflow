import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from lfx.components.processing.save_file import SaveToFileComponent
from lfx.schema import Data, Message
from tests.base import ComponentTestBaseWithoutClient

# TODO: Re-enable this test when the SaveToFileComponent is ready for use.
pytestmark = pytest.mark.skip(reason="Temporarily disabled")


class TestSaveToFileComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and teardown for each test."""
        # Setup
        test_files = [
            "./test_output.csv",
            "./test_output.xlsx",
            "./test_output.json",
            "./test_output.md",
            "./test_output.txt",
        ]
        # Teardown
        yield
        # Delete test files after each test
        for file_path in test_files:
            path = Path(file_path)
            if path.exists():
                path.unlink()

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return SaveToFileComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        sample_df = pd.DataFrame([{"col1": 1, "col2": "a"}, {"col1": 2, "col2": "b"}])
        return {"input_type": "DataFrame", "df": sample_df, "file_format": "csv", "file_path": "./test_output.csv"}

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        return []  # New component

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)
        assert component.input_type == "DataFrame"
        assert component.file_format == "csv"
        assert component.file_path == "./test_output.csv"

    def test_update_build_config_dataframe(self, component_class):
        """Test build config update for DataFrame input type."""
        component = component_class()
        build_config = {
            "df": {"show": False},
            "data": {"show": False},
            "message": {"show": False},
            "file_format": {"options": []},
        }

        updated_config = component.update_build_config(build_config, "DataFrame", "input_type")

        assert updated_config["df"]["show"] is True
        assert updated_config["data"]["show"] is False
        assert updated_config["message"]["show"] is False
        assert set(updated_config["file_format"]["options"]) == set(component.DATA_FORMAT_CHOICES)

    def test_save_message(self, component_class):
        """Test saving Message to different formats."""
        test_cases = [
            ("txt", "Test message"),
            ("json", json.dumps({"message": "Test message"}, indent=2)),
            ("markdown", "**Message:**\n\nTest message"),
        ]

        for fmt, expected_content in test_cases:
            mock_file = MagicMock()
            mock_parent = MagicMock()
            mock_parent.exists.return_value = True
            mock_file.parent = mock_parent
            mock_file.expanduser.return_value = mock_file

            # Mock Path at the module level where it's imported
            with patch("lfx.components.processing.save_to_file.Path") as mock_path:
                mock_path.return_value = mock_file

                component = component_class()
                component.set_attributes(
                    {
                        "input_type": "Message",
                        "message": Message(text="Test message"),
                        "file_format": fmt,
                        "file_path": f"./test_output.{fmt}",
                    }
                )

                result = component.save_to_file()

                mock_file.write_text.assert_called_once_with(expected_content, encoding="utf-8")
                assert "saved successfully" in result

    def test_save_data(self, component_class):
        """Test saving Data object to JSON."""
        test_data = {"col1": ["value1"], "col2": ["value2"]}

        mock_file = MagicMock()
        mock_parent = MagicMock()
        mock_parent.exists.return_value = True
        mock_file.parent = mock_parent
        mock_file.expanduser.return_value = mock_file

        with patch("lfx.components.processing.save_to_file.Path") as mock_path:
            mock_path.return_value = mock_file

            component = component_class()
            component.set_attributes(
                {
                    "input_type": "Data",
                    "data": Data(data=test_data),
                    "file_format": "json",
                    "file_path": "./test_output.json",
                }
            )

            result = component.save_to_file()

            expected_json = json.dumps(test_data, indent=2)
            mock_file.write_text.assert_called_once_with(expected_json, encoding="utf-8")
            assert "saved successfully" in result

    def test_directory_creation(self, component_class, default_kwargs):
        """Test directory creation if it doesn't exist."""
        mock_file = MagicMock()
        mock_parent = MagicMock()
        mock_parent.exists.return_value = False
        mock_file.parent = mock_parent
        mock_file.expanduser.return_value = mock_file

        with patch("lfx.components.processing.save_to_file.Path") as mock_path:
            mock_path.return_value = mock_file
            with patch.object(pd.DataFrame, "to_csv") as mock_to_csv:
                component = component_class()
                component.set_attributes(default_kwargs)

                result = component.save_to_file()

                mock_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
                assert mock_to_csv.called
                assert "saved successfully" in result

    def test_invalid_input_type(self, default_kwargs):
        """Test handling of invalid input type."""
        component = SaveToFileComponent()
        invalid_kwargs = default_kwargs.copy()  # Create a copy to modify
        invalid_kwargs["input_type"] = "InvalidType"
        component.set_attributes(invalid_kwargs)

        with pytest.raises(ValueError, match="Unsupported input type"):
            component.save_to_file()

    @pytest.mark.parametrize(
        ("path_str", "fmt", "expected_suffix"),
        [
            ("./test_output", "csv", ".csv"),
            ("./test_output", "json", ".json"),
            ("./test_output", "markdown", ".markdown"),
            ("./test_output", "txt", ".txt"),
        ],
    )
    def test_adjust_path_adds_extension(self, component_class, path_str, fmt, expected_suffix):
        """Test that the correct extension is added when none exists."""
        component = component_class()
        input_path = Path(path_str)
        expected_path = Path(f"{path_str}{expected_suffix}")
        result = component._adjust_file_path_with_format(input_path, fmt)
        assert str(result) == str(expected_path.expanduser())

    @pytest.mark.parametrize(
        ("path_str", "fmt"),
        [
            ("./test_output.csv", "csv"),
            ("./test_output.json", "json"),
            ("./test_output.markdown", "markdown"),
            ("./test_output.txt", "txt"),
        ],
    )
    def test_adjust_path_keeps_existing_correct_extension(self, component_class, path_str, fmt):
        """Test that the existing correct extension is kept."""
        component = component_class()
        input_path = Path(path_str)
        result = component._adjust_file_path_with_format(input_path, fmt)
        assert str(result) == str(input_path.expanduser())

    @pytest.mark.parametrize(
        ("path_str", "fmt", "expected_path_str"),
        [
            ("./test_output.txt", "csv", "./test_output.txt.csv"),  # Incorrect extension
            ("./test_output", "excel", "./test_output.xlsx"),  # Add .xlsx for excel
            ("./test_output.txt", "excel", "./test_output.txt.xlsx"),  # Incorrect extension for excel
        ],
    )
    def test_adjust_path_handles_incorrect_or_excel_add(self, component_class, path_str, fmt, expected_path_str):
        """Test handling incorrect extensions and adding .xlsx for excel."""
        component = component_class()
        input_path = Path(path_str)
        expected_path = Path(expected_path_str)
        result = component._adjust_file_path_with_format(input_path, fmt)
        assert str(result) == str(expected_path.expanduser())

    @pytest.mark.parametrize(
        "path_str",
        [
            "./test_output.xlsx",
            "./test_output.xls",
        ],
    )
    def test_adjust_path_keeps_existing_excel_extension(self, component_class, path_str):
        """Test that existing .xlsx or .xls extensions are kept for excel format."""
        component = component_class()
        input_path = Path(path_str)
        result = component._adjust_file_path_with_format(input_path, "excel")
        assert str(result) == str(input_path.expanduser())

    def test_adjust_path_expands_home(self, component_class):
        """Test that the home directory symbol '~' is expanded."""
        component = component_class()
        input_path = Path("~/test_output")
        expected_path = Path("~/test_output.csv").expanduser()
        result = component._adjust_file_path_with_format(input_path, "csv")
        assert str(result) == str(expected_path)
        assert "~" not in str(result)  # Ensure ~ was expanded

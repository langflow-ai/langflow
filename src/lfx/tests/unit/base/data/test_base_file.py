"""Tests for BaseFileComponent.load_files_message method."""

import json
import tempfile
from pathlib import Path

from lfx.base.data.base_file import BaseFileComponent
from lfx.schema.data import Data
from lfx.schema.message import Message


class TestFileComponent(BaseFileComponent):
    """Test implementation of BaseFileComponent for testing."""

    VALID_EXTENSIONS = ["txt", "json", "csv"]

    def __init__(self, **data):
        """Initialize with proper component setup."""
        super().__init__(**data)
        # Initialize the inputs to avoid AttributeError
        self.set_attributes(
            {
                "path": [],
                "file_path": None,
                "separator": "\n\n",
                "silent_errors": False,
                "delete_server_file_after_processing": True,
                "ignore_unsupported_extensions": True,
                "ignore_unspecified_files": False,
            }
        )

    def process_files(self, file_list):
        """Test implementation that creates Data objects from file content."""
        processed_files = []
        for file in file_list:
            if file.path.exists():
                content = file.path.read_text(encoding="utf-8")
                # Create Data objects based on file extension
                if file.path.suffix == ".json":
                    try:
                        json_data = json.loads(content)
                        data = Data(data=json_data)
                    except json.JSONDecodeError:
                        data = Data(data={"text": content, "file_path": str(file.path)})
                else:
                    data = Data(data={"text": content, "file_path": str(file.path)})

                file.data = [data]
            processed_files.append(file)
        return processed_files


class TestLoadFilesMessage:
    """Test cases for BaseFileComponent.load_files_message method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.component = TestFileComponent()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def teardown_method(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_load_files_message_empty_data(self):
        """Test load_files_message with no files returns empty Message."""
        # Set empty path
        self.component.path = []
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        # When no files are provided, load_files_core returns [Data()] which has data={}
        # When get_text() returns None/empty, the method falls back to orjson.dumps({})
        assert result.text in {"{}", ""}

    def test_load_files_message_with_simple_text_file(self):
        """Test load_files_message with a simple text file."""
        # Create a simple text file
        text_file = self.temp_path / "simple.txt"
        text_file.write_text("Hello world", encoding="utf-8")

        self.component.path = [str(text_file)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        assert result.text == "Hello world"

    def test_load_files_message_with_json_dict_content(self):
        """Test load_files_message with JSON file containing dict (simulates get_text() returning dict)."""
        # Create JSON file with dict content
        json_content = {"content": "dict content", "metadata": "extra info", "type": "test"}
        json_file = self.temp_path / "test.json"
        json_file.write_text(json.dumps(json_content), encoding="utf-8")

        self.component.path = [str(json_file)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        # Should contain the JSON content as string
        result_text = result.text
        assert "content" in result_text
        assert "dict content" in result_text
        assert "metadata" in result_text

    def test_load_files_message_with_multiple_files(self):
        """Test load_files_message with multiple files."""
        # Create multiple text files
        file1 = self.temp_path / "first.txt"
        file1.write_text("First text", encoding="utf-8")

        file2 = self.temp_path / "second.txt"
        file2.write_text("Second text", encoding="utf-8")

        self.component.path = [str(file1), str(file2)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        assert "First text" in result.text
        assert "Second text" in result.text
        assert "\n\n" in result.text  # Default separator

    def test_load_files_message_with_custom_separator(self):
        """Test load_files_message with custom separator."""
        self.component.separator = " | "

        # Create two text files
        file1 = self.temp_path / "first.txt"
        file1.write_text("First", encoding="utf-8")

        file2 = self.temp_path / "second.txt"
        file2.write_text("Second", encoding="utf-8")

        self.component.path = [str(file1), str(file2)]
        result = self.component.load_files_message()

        assert result.text == "First | Second"

    def test_load_files_message_with_json_complex_structure(self):
        """Test load_files_message with complex JSON structure."""
        complex_data = {
            "metadata": {"type": "document", "version": 1},
            "properties": {"author": "test", "date": "2024-01-01"},
            "content": "This should be extracted",
        }
        json_file = self.temp_path / "complex.json"
        json_file.write_text(json.dumps(complex_data), encoding="utf-8")

        self.component.path = [str(json_file)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        # Should contain the extracted content field
        assert "This should be extracted" in result.text

    def test_load_files_message_with_json_no_common_fields(self):
        """Test with JSON that has no common text fields (should use orjson.dumps)."""
        complex_data = {
            "metadata": {"type": "document", "version": 1},
            "properties": {"author": "test", "date": "2024-01-01"},
            # No "text", "content", "value", or "message" fields
        }
        json_file = self.temp_path / "no_text_fields.json"
        json_file.write_text(json.dumps(complex_data), encoding="utf-8")

        self.component.path = [str(json_file)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        # Should contain JSON representation since no common text fields found
        assert "metadata" in result.text
        assert "properties" in result.text
        assert "author" in result.text

    def test_load_files_message_with_none_separator(self):
        r"""Test load_files_message when separator is None (should default to \\n\\n)."""
        self.component.separator = None

        file1 = self.temp_path / "first.txt"
        file1.write_text("First", encoding="utf-8")

        file2 = self.temp_path / "second.txt"
        file2.write_text("Second", encoding="utf-8")

        self.component.path = [str(file1), str(file2)]
        result = self.component.load_files_message()

        # Should default to "\n\n" when separator is None
        assert result.text == "First\n\nSecond"

    def test_load_files_message_ensures_all_parts_are_strings(self):
        """Test that the method never tries to join non-string elements (core bug test)."""
        # Create a mixed content scenario - JSON with dict content
        dict_content = {"nested": {"data": "value"}, "another": "dict"}
        json_file = self.temp_path / "mixed_content.json"
        json_file.write_text(json.dumps(dict_content), encoding="utf-8")

        self.component.path = [str(json_file)]

        # This should not raise "sequence item 0: expected str instance, dict found"
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        assert isinstance(result.text, str)
        # Verify the content was properly converted to string
        assert len(result.text) > 0
        assert "nested" in result.text or "another" in result.text

    def test_load_files_message_extract_common_text_fields(self):
        """Test extraction of common text fields like 'content', 'value', 'message'."""
        test_cases = [
            ({"content": "Content text"}, "Content text"),
            ({"value": "Value text"}, "Value text"),
            ({"message": "Message text"}, "Message text"),
            ({"some_field": "ignored", "content": "Content wins"}, "Content wins"),
        ]

        for i, (data_dict, expected_text) in enumerate(test_cases):
            json_file = self.temp_path / f"test_field_{i}.json"
            json_file.write_text(json.dumps(data_dict), encoding="utf-8")

            self.component.path = [str(json_file)]
            result = self.component.load_files_message()

            assert isinstance(result, Message)
            assert expected_text in result.text

    def test_load_files_message_mixed_file_types(self):
        """Test mixed scenarios with text files and JSON files."""
        # Create text file
        text_file = self.temp_path / "text_response.txt"
        text_file.write_text("String response", encoding="utf-8")

        # Create JSON file with dict content
        json_file = self.temp_path / "json_response.json"
        json_file.write_text(json.dumps({"parsed": "Dict content"}), encoding="utf-8")

        # Create JSON file with content field
        content_file = self.temp_path / "content_response.json"
        content_file.write_text(json.dumps({"content": "Field extraction"}), encoding="utf-8")

        self.component.path = [str(text_file), str(json_file), str(content_file)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        result_text = result.text
        assert "String response" in result_text
        assert "Field extraction" in result_text
        # JSON content should be present in some form
        assert "parsed" in result_text or "Dict content" in result_text


class TestResolvePathsFromValue:
    """Test cases for BaseFileComponent._resolve_paths_from_value method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.component = TestFileComponent()
        self.component.set_attributes({"file_path": None, "path": []})

    def test_resolve_data_object_with_text_field(self):
        """Data object with text field containing path should be resolved."""
        data = Data(data={"text": "/test/path.txt"})
        paths = self.component._resolve_paths_from_value(data)

        assert len(paths) == 1
        resolved_data, path_str = paths[0]
        assert path_str == "/test/path.txt"
        assert resolved_data is data  # Should return the original Data object

    def test_resolve_stringified_json_array(self):
        """JSON array string should be parsed into individual paths."""
        json_str = '["/path/a.txt", "/path/b.txt"]'
        paths = self.component._resolve_paths_from_value(json_str)

        assert len(paths) == 2
        assert paths[0][1] == "/path/a.txt"
        assert paths[1][1] == "/path/b.txt"
        assert paths[0][0].data["file_path"] == "/path/a.txt"

    def test_resolve_double_encoded_json(self):
        """Double-encoded JSON should be handled gracefully."""
        # A JSON string that encodes another JSON string
        double_encoded = json.dumps(json.dumps(["/path/double.txt"]))
        paths = self.component._resolve_paths_from_value(double_encoded)

        assert len(paths) == 1
        assert paths[0][1] == "/path/double.txt"

    def test_resolve_malformed_json_fallback(self):
        """Malformed JSON should be treated as literal string."""
        malformed = '["/path/a.txt", missing_quote]'
        paths = self.component._resolve_paths_from_value(malformed)

        assert len(paths) == 1
        assert paths[0][1] == '["/path/a.txt", missing_quote]'

    def test_resolve_empty_values(self):
        """Empty string, None, and empty list should return empty list."""
        assert self.component._resolve_paths_from_value("") == []
        assert self.component._resolve_paths_from_value(None) == []
        assert self.component._resolve_paths_from_value([]) == []

    def test_resolve_path_object(self):
        """Path objects should be resolved to strings."""
        path_obj = Path("/test/path_obj.txt")
        paths = self.component._resolve_paths_from_value(path_obj)

        assert len(paths) == 1
        assert paths[0][1] == "/test/path_obj.txt"

    def test_resolve_mixed_list(self):
        """List containing mix of Data objects and strings."""
        data1 = Data(data={"text": "/list/data1.txt"})
        data2 = Data(data={"text": "/list/data2.txt"})
        mixed_list = [data1, "/list/str.txt", data2]

        paths = self.component._resolve_paths_from_value(mixed_list)

        assert len(paths) == 3
        assert paths[0][1] == "/list/data1.txt"
        assert paths[1][1] == "/list/str.txt"
        assert paths[2][1] == "/list/data2.txt"

    def test_resolve_data_object_no_fields(self):
        """Data object with no recognized path fields should not yield a path."""
        data = Data(data={"other_field": "value"})
        paths = self.component._resolve_paths_from_value(data)

        # Assuming it gets skipped or yields an empty string if get_text() returns None
        # From tracing the code, it uses format_text() which might return a repr if text isn't found,
        # or None if get_text() is overridden. Let's see what it actually does.
        # In base_file, if path_str is empty we skip processing.
        # But wait, data.data.get("text") might be None. get_text() usually returns data.get("text", "").
        assert len(paths) == 0


class TestFilePathAsList:
    """Test cases for BaseFileComponent._file_path_as_list method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.component = TestFileComponent()

    def test_file_path_none(self):
        """If file_path is None, returns an empty list."""
        self.component.set_attributes({"file_path": None, "path": []})
        result = self.component._file_path_as_list()
        assert result == []

    def test_file_path_single_data(self):
        """If file_path is a single Data object, returns list with it."""
        data = Data(data={"text": "/test/file.txt"})
        self.component.set_attributes({"file_path": data, "path": []})
        result = self.component._file_path_as_list()

        assert len(result) == 1
        assert result[0] is not data  # It creates a new copy to avoid shared mutation
        assert result[0].data["text"] == "/test/file.txt"
        assert result[0].data["file_path"] == "/test/file.txt"

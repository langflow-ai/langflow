"""Tests for BaseFileComponent.load_files_message method."""

import json
import tempfile
import threading
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


class TestDeleteAfterProcessingRaceCondition:
    """Tests for race condition when delete_server_file_after_processing=True."""

    def setup_method(self):
        """Set up test fixtures."""
        self.component = TestFileComponent()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def teardown_method(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_concurrent_output_calls_share_processed_result_when_delete_after_processing(self):
        """Concurrent output calls share the cached parsed result after the server file is gone.

        When delete_after_processing=True and the server file has already been deleted by a
        prior output call on the same component instance, load_files_base must return the cached
        processed result so downstream outputs receive the same parsed data instead of empty Data.

        This covers the race condition where a File component with multiple connected outputs
        invokes load_files_base() more than once: the first call processes and deletes the
        server file; the second call must neither raise nor silently drop output data.
        """
        # Create a real file with known content
        server_file = self.temp_path / "server_file.txt"
        server_file.write_text("content", encoding="utf-8")

        # Set up the component with the server file path via file_path Data input
        file_data = Data(data={"file_path": str(server_file)})
        self.component.file_path = file_data
        self.component.delete_server_file_after_processing = True
        self.component.silent_errors = False  # Ensure errors would normally propagate

        # First call: processes and deletes the file
        first_result = self.component.load_files_base()
        assert not server_file.exists(), "File should have been deleted after first call"
        assert first_result, "First call should return non-empty parsed data"

        # Second call: file is already gone; should NOT raise and must NOT drop the data.
        # The cached processed result from the first call should be returned so a second
        # downstream output sees the same content rather than an empty Data wrapper.
        second_result = self.component.load_files_base()
        assert second_result == first_result, (
            "Second call on deleted server file must return the cached processed data "
            "(not an empty list), to preserve output correctness for concurrent outputs."
        )

    def test_validate_raises_for_missing_file_when_not_delete_after_processing(self):
        """When delete_after_processing=False, a missing file should still raise ValueError.

        Exercises the ``file_path`` decision branch in load_files_base (not the ``self.path``
        branch) so the non-race-condition error path is covered for server-file inputs.
        """
        missing_path = self.temp_path / "nonexistent.txt"

        self.component.file_path = Data(data={"file_path": str(missing_path)})
        self.component.delete_server_file_after_processing = False
        self.component.silent_errors = False

        import pytest

        with pytest.raises(ValueError, match="File not found"):
            self.component.load_files_base()

    def test_concurrent_output_calls_are_serialized(self):
        """Concurrent load_files_base() calls on the same instance must share parsed data.

        Exercises the lock + keyed cache path: two threads enter load_files_base at the
        same time. Only one should execute the read+process+delete cycle; the other must
        observe the cached parsed result rather than racing past validation and producing
        empty output.
        """
        server_file = self.temp_path / "concurrent_file.txt"
        server_file.write_text("concurrent-content", encoding="utf-8")

        self.component.file_path = Data(data={"file_path": str(server_file)})
        self.component.delete_server_file_after_processing = True
        self.component.silent_errors = False

        results: list[list[Data]] = []
        errors: list[BaseException] = []
        barrier = threading.Barrier(2)

        def worker():
            try:
                barrier.wait(timeout=5)
                results.append(self.component.load_files_base())
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Concurrent load_files_base() raised: {errors!r}"
        assert len(results) == 2
        assert results[0], "First completed call should return non-empty parsed data"
        assert results[0] == results[1], (
            "Concurrent calls must return identical parsed data — neither caller should "
            "silently fall through to empty output when the other deletes the server file."
        )
        assert not server_file.exists(), "Server file should have been deleted exactly once"

    def test_cache_does_not_pollute_legitimate_empty_input(self):
        """An empty validation result (no input configured) must not return stale cached data.

        Covers the secondary blocker: race-recovery should only activate when validation
        actually skipped a missing ``delete_after_processing=True`` server file, not for
        every empty validation result.
        """
        # Configure a fresh component with no inputs at all.
        self.component.file_path = None
        self.component.path = []
        self.component.delete_server_file_after_processing = True

        # First call has no input → returns empty without populating recovery cache.
        first = self.component.load_files_base()
        assert first == [], "Empty input should yield empty output, not stale cache"

        # Now simulate that a *different* prior call did populate the cache for some
        # other set of paths. The empty-input call must not pick that up.
        cached_data = [Data(data={"text": "stale", "file_path": "/tmp/old.txt"})]
        self.component._load_files_base_processed_cache = {  # type: ignore[attr-defined]
            ((), ("/tmp/old.txt",), False): cached_data,
        }

        second = self.component.load_files_base()
        assert second == [], (
            "Race-recovery must be keyed to the current paths and gated on the "
            "validation-skip flag; an empty input must not return a stale cached result."
        )

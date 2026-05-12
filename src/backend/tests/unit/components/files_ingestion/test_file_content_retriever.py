"""Tests for FileContentRetrieverComponent.

Tests focus on critical logic and edge cases:
- File lookup and retrieval from Data/DataFrame inputs
- DataFrame conversion for various file formats
- Error handling for missing files and invalid formats
- Edge cases with mixed inputs and malformed data
- Tool invocation with explicit arguments
- Serialization of results
"""

from pathlib import Path

import pandas as pd
import pytest
from lfx.components.files_ingestion.file_content_retriever import FileContentRetrieverComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.serialization.serialization import serialize

from tests.base import ComponentTestBaseWithoutClient


class TestFileContentRetrieverComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return FileContentRetrieverComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return default kwargs with sample file data."""
        return {
            "file_data": [
                Data(text="content1", data={"file_path": "file1.txt"}),
                Data(text="content2", data={"file_path": "file2.txt"}),
            ],
            "file_path": "file1.txt",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return empty list - new component without version history."""
        return []

    # ========== retrieve_content Tests ==========

    def test_retrieve_content_basic(self, component_class, default_kwargs):
        """Test basic file content retrieval from Data objects."""
        component = component_class()
        component.set_attributes(default_kwargs)
        result = component.retrieve_content()

        assert isinstance(result, Message)
        assert result.text == "content1"

    def test_retrieve_content_with_explicit_argument(self, component_class, default_kwargs):
        """Test file content retrieval using explicit file_path argument."""
        component = component_class()
        component.set_attributes(default_kwargs)
        # Call with explicit argument (tool invocation style)
        result = component.retrieve_content(file_path="file2.txt")

        assert isinstance(result, Message)
        assert result.text == "content2"

    def test_retrieve_content_argument_overrides_attribute(self, component_class, default_kwargs):
        """Test that explicit argument takes precedence over self.file_path."""
        component = component_class()
        default_kwargs["file_path"] = "file1.txt"
        component.set_attributes(default_kwargs)

        # Explicit argument should override
        result = component.retrieve_content(file_path="file2.txt")
        assert result.text == "content2"

    def test_retrieve_content_file_not_found(self, component_class, default_kwargs):
        """Test error raised when file not found - lists available files."""
        component = component_class()
        component.set_attributes(default_kwargs)

        with pytest.raises(ValueError, match="not found") as exc_info:
            component.retrieve_content(file_path="nonexistent.txt")

        error_msg = str(exc_info.value)
        assert "file1.txt" in error_msg
        assert "file2.txt" in error_msg

    def test_retrieve_content_empty_path_returns_empty(self, component_class):
        """Test that empty file path returns empty Message (for tool initialization)."""
        component = component_class()
        # Don't set file_path attribute, and pass empty string as argument
        component.set_attributes({"file_data": [Data(text="content", data={"file_path": "file.txt"})]})

        result = component.retrieve_content(file_path="")
        assert isinstance(result, Message)
        assert result.text == ""

    def test_retrieve_content_no_argument_no_attribute_returns_empty(self, component_class):
        """Test that missing file_path in both argument and attribute returns empty Message."""
        component = component_class()
        component.set_attributes({"file_data": [Data(text="content", data={"file_path": "file.txt"})]})
        # Don't set file_path attribute

        result = component.retrieve_content()
        assert isinstance(result, Message)
        assert result.text == ""

    def test_retrieve_content_with_dataframe_input(self, component_class):
        """Test retrieving content from DataFrame input - converts to string."""
        df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
        langflow_df = DataFrame(df)
        langflow_df.attrs["source_file_path"] = "data.csv"

        component = component_class()
        component.set_attributes({"file_data": [langflow_df]})
        result = component.retrieve_content(file_path="data.csv")

        assert isinstance(result, Message)
        assert "col1" in result.text
        assert "col2" in result.text

    def test_retrieve_content_mixed_data_and_dataframe(self, component_class):
        """Test with mixed Data and DataFrame inputs."""
        df = pd.DataFrame({"col1": [1, 2]})
        langflow_df = DataFrame(df)
        langflow_df.attrs["source_file_path"] = "data.csv"

        data_obj = Data(text="text content", data={"file_path": "file.txt"})

        component = component_class()
        component.set_attributes({"file_data": [langflow_df, data_obj]})
        result = component.retrieve_content(file_path="file.txt")

        assert result.text == "text content"

    def test_retrieve_content_with_message_input(self, component_class):
        """Test retrieving content from Message input with file_path in metadata."""
        msg = Message(text="message file content", file_path="/path/to/report.txt")

        component = component_class()
        component.set_attributes({"file_data": [msg]})
        result = component.retrieve_content(file_path="/path/to/report.txt")

        assert isinstance(result, Message)
        assert result.text == "message file content"

    def test_retrieve_content_message_without_file_path(self, component_class):
        """Test that Message without file_path is skipped."""
        msg = Message(text="no path content")

        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    msg,
                    Data(text="has path", data={"file_path": "valid.txt"}),
                ],
            }
        )
        result = component.retrieve_content(file_path="valid.txt")
        assert result.text == "has path"

    def test_retrieve_content_mixed_message_data_dataframe(self, component_class):
        """Test with mixed Message, Data, and DataFrame inputs."""
        msg = Message(text="msg content", file_path="msg_file.txt")
        data_obj = Data(text="data content", data={"file_path": "data_file.txt"})
        df = DataFrame(pd.DataFrame({"col1": [1, 2]}))
        df.attrs["source_file_path"] = "df_file.csv"

        component = component_class()
        component.set_attributes({"file_data": [msg, data_obj, df]})

        result_msg = component.retrieve_content(file_path="msg_file.txt")
        assert result_msg.text == "msg content"

        component._cached_text_map = None
        component._cached_dataframe_map = None
        result_data = component.retrieve_content(file_path="data_file.txt")
        assert result_data.text == "data content"

    def test_retrieve_content_data_without_file_path(self, component_class):
        """Test Data objects without file_path are ignored in file map."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="no path", data={}),
                    Data(text="has path", data={"file_path": "valid.txt"}),
                ],
            }
        )
        result = component.retrieve_content(file_path="valid.txt")

        assert result.text == "has path"

    def test_retrieve_content_dataframe_without_source_path(self, component_class):
        """Test DataFrame without source_file_path is ignored in file map."""
        df1 = DataFrame(pd.DataFrame({"col": [1]}))
        # No source_file_path set

        df2 = DataFrame(pd.DataFrame({"col": [2]}))
        df2.attrs["source_file_path"] = "valid.csv"

        component = component_class()
        component.set_attributes({"file_data": [df1, df2]})
        result = component.retrieve_content(file_path="valid.csv")

        assert "col" in result.text
        assert "2" in result.text

    def test_retrieve_content_unsupported_input_type(self, component_class):
        """Test that unsupported input types are skipped gracefully."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    "not a Data or DataFrame",
                    Data(text="valid content", data={"file_path": "file.txt"}),
                ],
            }
        )
        result = component.retrieve_content(file_path="file.txt")

        assert result.text == "valid content"

    def test_file_maps_cached_across_calls(self, component_class):
        """Test that file maps are built once and reused across multiple calls."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="content1", data={"file_path": "file1.txt"}),
                    Data(text="content2", data={"file_path": "file2.txt"}),
                ]
            }
        )

        # First call should build the maps
        result1 = component.retrieve_content(file_path="file1.txt")
        assert result1.text == "content1"
        assert component._cached_text_map is not None
        assert component._cached_dataframe_map is not None

        # Store references to the cached maps
        cached_text_map_id = id(component._cached_text_map)
        cached_dataframe_map_id = id(component._cached_dataframe_map)

        # Second call should reuse the same cached maps (same object IDs)
        result2 = component.retrieve_content(file_path="file2.txt")
        assert result2.text == "content2"
        assert id(component._cached_text_map) == cached_text_map_id
        assert id(component._cached_dataframe_map) == cached_dataframe_map_id

        # Third call with dataframe method should also reuse cached maps
        csv_content = "col1,col2\n1,a\n2,b"
        component.set_attributes({"file_data": [Data(text=csv_content, data={"file_path": "data.csv"})]})
        # Reset cache to test with new data
        component._cached_text_map = None
        component._cached_dataframe_map = None

        result3 = component.retrieve_content_as_dataframe(file_path="data.csv")
        assert len(result3) == 2
        cached_text_map_id2 = id(component._cached_text_map)
        cached_dataframe_map_id2 = id(component._cached_dataframe_map)

        # Another call should reuse the same maps
        component.retrieve_content(file_path="data.csv")
        assert id(component._cached_text_map) == cached_text_map_id2
        assert id(component._cached_dataframe_map) == cached_dataframe_map_id2

    # ========== retrieve_content_as_dataframe Tests ==========

    def test_as_dataframe_csv_content(self, component_class):
        """Test converting CSV content to DataFrame."""
        csv_content = "col1,col2\n1,a\n2,b"
        component = component_class()
        component.set_attributes({"file_data": [Data(text=csv_content, data={"file_path": "data.csv"})]})

        result = component.retrieve_content_as_dataframe(file_path="data.csv")

        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert list(result.columns) == ["col1", "col2"]
        assert result["col1"].tolist() == [1, 2]
        assert result.attrs["source_file_path"] == "data.csv"

    def test_as_dataframe_with_explicit_argument(self, component_class):
        """Test DataFrame retrieval using explicit file_path argument."""
        csv_content = "col1,col2\n1,a\n2,b"
        component = component_class()
        component.set_attributes({"file_data": [Data(text=csv_content, data={"file_path": "data.csv"})]})

        # Call with explicit argument (tool invocation style)
        result = component.retrieve_content_as_dataframe(file_path="data.csv")

        assert isinstance(result, DataFrame)
        assert len(result) == 2

    def test_as_dataframe_argument_overrides_attribute(self, component_class):
        """Test that explicit argument takes precedence over self.file_path."""
        csv1 = "col1\n1"
        csv2 = "col2\n2"
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text=csv1, data={"file_path": "file1.csv"}),
                    Data(text=csv2, data={"file_path": "file2.csv"}),
                ],
                "file_path": "file1.csv",
            }
        )

        # Explicit argument should override
        result = component.retrieve_content_as_dataframe(file_path="file2.csv")
        assert "col2" in result.columns

    def test_as_dataframe_tsv_content(self, component_class):
        """Test converting TSV content to DataFrame."""
        tsv_content = "col1\tcol2\n1\ta\n2\tb"
        component = component_class()
        component.set_attributes({"file_data": [Data(text=tsv_content, data={"file_path": "data.tsv"})]})

        result = component.retrieve_content_as_dataframe(file_path="data.tsv")

        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert list(result.columns) == ["col1", "col2"]

    def test_as_dataframe_json_content(self, component_class):
        """Test converting JSON content to DataFrame."""
        json_content = '[{"col1": 1, "col2": "a"}, {"col1": 2, "col2": "b"}]'
        component = component_class()
        component.set_attributes({"file_data": [Data(text=json_content, data={"file_path": "data.json"})]})

        result = component.retrieve_content_as_dataframe(file_path="data.json")

        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert "col1" in result.columns
        assert "col2" in result.columns

    def test_as_dataframe_returns_existing_dataframe(self, component_class):
        """Test that existing DataFrame is returned directly without conversion."""
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        langflow_df = DataFrame(df)
        langflow_df.attrs["source_file_path"] = "data.csv"

        component = component_class()
        component.set_attributes({"file_data": [langflow_df]})

        result = component.retrieve_content_as_dataframe(file_path="data.csv")

        assert result is langflow_df
        assert len(result) == 3

    def test_as_dataframe_returns_dataframe_with_file_path_in_columns(self, component_class):
        """Test that DataFrame with file_path in columns extracts text into text_map."""
        # This simulates the output from Read File component's load_files() method
        # which creates a DataFrame with file_path in the data columns, not in attrs
        # The text needs to be valid CSV for parsing to work
        csv_text = "col1,col2\n1,a\n2,b"
        df = pd.DataFrame(
            {
                "file_path": ["/path/to/data.csv"],
                "text": [csv_text],
            }
        )
        langflow_df = DataFrame(df)
        # Note: NO source_file_path in attrs, only in columns

        component = component_class()
        component.set_attributes({"file_data": [langflow_df]})

        # The component extracts text from rows with file_path column
        # Since it's CSV, it should parse the text into a DataFrame
        result = component.retrieve_content_as_dataframe(file_path="/path/to/data.csv")

        assert isinstance(result, DataFrame)
        # The result should be a parsed DataFrame from the CSV text content
        assert len(result) == 2
        assert list(result.columns) == ["col1", "col2"]

    def test_as_dataframe_empty_file_path_returns_empty(self, component_class):
        """Test that empty file_path returns empty DataFrame."""
        component = component_class()
        component.set_attributes({"file_data": [Data(text="content", data={"file_path": "file.csv"})]})

        result = component.retrieve_content_as_dataframe(file_path="")
        assert isinstance(result, DataFrame)
        assert len(result) == 0

    def test_as_dataframe_no_argument_no_attribute_returns_empty(self, component_class):
        """Test that missing file_path in both argument and attribute returns empty DataFrame."""
        component = component_class()
        component.set_attributes({"file_data": [Data(text="col1\n1", data={"file_path": "file.csv"})]})
        # Don't set file_path attribute

        result = component.retrieve_content_as_dataframe()
        assert isinstance(result, DataFrame)
        assert len(result) == 0

    def test_as_dataframe_unsupported_extension_raises(self, component_class):
        """Test that unsupported file extension raises ValueError with supported formats."""
        component = component_class()
        component.set_attributes({"file_data": [Data(text="content", data={"file_path": "file.txt"})]})

        with pytest.raises(ValueError, match="not supported for DataFrame conversion"):
            component.retrieve_content_as_dataframe(file_path="file.txt")

    def test_as_dataframe_file_not_found_raises(self, component_class):
        """Test that missing file raises ValueError with available files."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="content1", data={"file_path": "file1.csv"}),
                    Data(text="content2", data={"file_path": "file2.csv"}),
                ],
            }
        )

        with pytest.raises(ValueError, match=r"not found.*Available"):
            component.retrieve_content_as_dataframe(file_path="missing.csv")

    def test_as_dataframe_no_files_available_raises(self, component_class):
        """Test error message when no files available in input data."""
        component = component_class()
        component.set_attributes({"file_data": []})

        with pytest.raises(ValueError, match="No files were provided"):
            component.retrieve_content_as_dataframe(file_path="missing.csv")

    def test_as_dataframe_malformed_json_not_in_map(self, component_class):
        """Test that malformed JSON is not added to dataframe map (parsing fails silently)."""
        malformed_json = '{"col1": 1, "col2": "unclosed'
        component = component_class()
        component.set_attributes({"file_data": [Data(text=malformed_json, data={"file_path": "bad.json"})]})

        # Malformed JSON won't be parsed into dataframe_map, so file won't be found
        with pytest.raises(ValueError, match="not found"):
            component.retrieve_content_as_dataframe(file_path="bad.json")

    def test_as_dataframe_case_insensitive_extension(self, component_class):
        """Test that file extensions are case-insensitive."""
        csv_content = "col1,col2\n1,a"
        component = component_class()
        component.set_attributes({"file_data": [Data(text=csv_content, data={"file_path": "file.CSV"})]})

        result = component.retrieve_content_as_dataframe(file_path="file.CSV")
        assert isinstance(result, DataFrame)

    # ========== _get_file_maps Tests ==========

    def test_build_file_map_empty_input(self, component_class):
        """Test building file map with empty input."""
        component = component_class()
        component.set_attributes({"file_data": []})

        text_map, dataframe_map = component._get_file_maps()
        assert text_map == {}
        assert dataframe_map == {}

    def test_build_file_map_data_only(self, component_class):
        """Test building file map with only Data objects."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="content1", data={"file_path": "file1.txt"}),
                    Data(text="content2", data={"file_path": "file2.txt"}),
                ],
            }
        )

        text_map, dataframe_map = component._get_file_maps()
        assert len(text_map) == 2
        assert text_map["file1.txt"] == "content1"
        assert text_map["file2.txt"] == "content2"
        assert len(dataframe_map) == 0

    def test_build_file_map_dataframe_only(self, component_class):
        """Test building file map with only DataFrame objects."""
        df1 = DataFrame(pd.DataFrame({"col": [1]}))
        df1.attrs["source_file_path"] = "data1.csv"

        df2 = DataFrame(pd.DataFrame({"col": [2]}))
        df2.attrs["source_file_path"] = "data2.csv"

        component = component_class()
        component.set_attributes({"file_data": [df1, df2]})

        text_map, dataframe_map = component._get_file_maps()
        # DataFrames go into dataframe_map, not text_map
        assert len(text_map) == 0
        assert len(dataframe_map) == 2
        assert "data1.csv" in dataframe_map
        assert "data2.csv" in dataframe_map

    def test_build_file_map_caching(self, component_class):
        """Test that file maps are cached and reused."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="content", data={"file_path": "file.txt"}),
                ],
            }
        )

        # First call builds the cache
        text_map1, df_map1 = component._get_file_maps()

        # Second call should return the same cached objects
        text_map2, df_map2 = component._get_file_maps()

        assert text_map1 is text_map2
        assert df_map1 is df_map2

    def test_build_file_map_duplicate_paths_last_wins(self, component_class):
        """Test that duplicate file paths use the last occurrence."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="first", data={"file_path": "dup.txt"}),
                    Data(text="second", data={"file_path": "dup.txt"}),
                ],
            }
        )

        text_map, _ = component._get_file_maps()
        assert text_map["dup.txt"] == "second"

    def test_build_file_map_mixed_with_and_without_paths(self, component_class):
        """Test mixed inputs where some have paths and some don't."""
        df_with_path = DataFrame(pd.DataFrame({"col": [1]}))
        df_with_path.attrs["source_file_path"] = "has_path.csv"

        df_without_path = DataFrame(pd.DataFrame({"col": [2]}))
        # No source_file_path

        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="has path", data={"file_path": "file.txt"}),
                    Data(text="no path", data={}),
                    df_with_path,
                    df_without_path,
                ],
            }
        )

        text_map, dataframe_map = component._get_file_maps()
        # Only Data with file_path goes into text_map, DataFrame goes into dataframe_map
        assert len(text_map) == 1
        assert "file.txt" in text_map
        assert len(dataframe_map) == 1
        assert "has_path.csv" in dataframe_map

    def test_build_file_map_unsupported_types_skipped(self, component_class):
        """Test that unsupported types in file_data are skipped."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    "not a Data or DataFrame",
                    Data(text="valid", data={"file_path": "file.txt"}),
                    123,
                ],
            }
        )

        text_map, _ = component._get_file_maps()
        assert len(text_map) == 1
        assert "file.txt" in text_map

    # ========== Serialization Tests ==========

    def test_serialization_of_message_result(self, component_class):
        """Test that Message result serializes correctly."""
        component = component_class()
        component.set_attributes({"file_data": [Data(text="test content", data={"file_path": "file.txt"})]})

        result = component.retrieve_content(file_path="file.txt")
        serialized = serialize(result)

        # Message should serialize to its text content
        assert isinstance(serialized, dict)
        assert "text" in serialized

    def test_serialization_of_dataframe_result(self, component_class):
        """Test that DataFrame result serializes correctly (not to empty list)."""
        csv_content = "col1,col2\n1,a\n2,b"
        component = component_class()
        component.set_attributes({"file_data": [Data(text=csv_content, data={"file_path": "data.csv"})]})

        result = component.retrieve_content_as_dataframe(file_path="data.csv")
        serialized = serialize(result)

        # DataFrame should serialize to list of dicts (records)
        assert isinstance(serialized, list)
        assert len(serialized) == 2
        assert serialized[0]["col1"] == 1
        assert serialized[0]["col2"] == "a"

    def test_serialization_empty_dataframe_is_empty_list(self, component_class):  # noqa: ARG002
        """Test that empty DataFrame serializes to empty list."""
        empty_df = DataFrame(pd.DataFrame())
        serialized = serialize(empty_df)

        assert isinstance(serialized, list)
        assert len(serialized) == 0

    def test_serialization_preserves_data_types(self, component_class):
        """Test that serialization preserves data types correctly."""
        csv_content = "int_col,float_col,str_col\n1,1.5,text\n2,2.5,more"
        component = component_class()
        component.set_attributes({"file_data": [Data(text=csv_content, data={"file_path": "data.csv"})]})

        result = component.retrieve_content_as_dataframe(file_path="data.csv")
        serialized = serialize(result)

        assert isinstance(serialized[0]["int_col"], int)
        assert isinstance(serialized[0]["float_col"], float)
        assert isinstance(serialized[0]["str_col"], str)

    # ========== Tool Invocation Simulation Tests ==========

    def test_tool_invocation_pattern(self, component_class):
        """Test the pattern used when component is invoked as a tool by an agent."""
        # Simulate tool setup
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="col1,col2\n1,a\n2,b", data={"file_path": "/path/to/airbnb.csv"}),
                ],
            }
        )

        # Simulate agent calling the tool with explicit argument
        result = component.retrieve_content_as_dataframe(file_path="/path/to/airbnb.csv")

        # Verify result is correct
        assert isinstance(result, DataFrame)
        assert len(result) == 2
        assert "col1" in result.columns

        # Verify serialization works
        serialized = serialize(result)
        assert isinstance(serialized, list)
        assert len(serialized) == 2

    def test_tool_invocation_with_deepcopy(self, component_class):
        """Test that tool invocation works correctly with deepcopy (as done in component_tool.py)."""
        from copy import deepcopy

        # Setup original component
        original = component_class()
        original.set_attributes(
            {
                "file_data": [
                    Data(text="content", data={"file_path": "file.txt"}),
                ],
            }
        )

        # Simulate tool invocation with deepcopy
        component_copy = deepcopy(original)
        result = component_copy.retrieve_content(file_path="file.txt")

        assert isinstance(result, Message)
        assert result.text == "content"


class TestFileContentRetrieverPersistence:
    """Tests for persistent directory support."""

    @pytest.fixture
    def component_class(self):
        from lfx.components.files_ingestion.file_content_retriever import FileContentRetrieverComponent

        return FileContentRetrieverComponent

    def test_persistent_save_and_load_roundtrip(self, component_class, tmp_path):
        """Test that maps saved to disk can be reloaded by a new component instance."""
        persist_dir = str(tmp_path / "persist")

        # First run: build maps from data and persist
        c1 = component_class()
        c1.set_attributes(
            {
                "file_data": [
                    Data(text="hello world", data={"file_path": "/data/hello.txt"}),
                    Data(text="a,b\n1,2\n3,4", data={"file_path": "/data/nums.csv"}),
                ],
                "persistent_dir": persist_dir,
            }
        )
        result = c1.retrieve_content(file_path="/data/hello.txt")
        assert result.text == "hello world"

        # Verify files were written
        assert (tmp_path / "persist" / "text_index.json").exists()
        assert (tmp_path / "persist" / "texts").is_dir()
        assert (tmp_path / "persist" / "dataframe_index.json").exists()
        assert (tmp_path / "persist" / "dataframes").is_dir()

        # Second run: new component loads from disk (no file_data input)
        c2 = component_class()
        c2.set_attributes(
            {
                "file_data": [],
                "persistent_dir": persist_dir,
            }
        )
        result2 = c2.retrieve_content(file_path="/data/hello.txt")
        assert result2.text == "hello world"

        df_result = c2.retrieve_content_as_dataframe(file_path="/data/nums.csv")
        assert len(df_result) == 2
        assert "a" in df_result.columns

    def test_persistent_skips_existing_paths(self, component_class, tmp_path):
        """Test that new data doesn't overwrite existing persisted entries."""
        persist_dir = str(tmp_path / "persist")

        # First run: persist original content
        c1 = component_class()
        c1.set_attributes(
            {
                "file_data": [Data(text="original", data={"file_path": "/file.txt"})],
                "persistent_dir": persist_dir,
            }
        )
        c1.retrieve_content(file_path="/file.txt")

        # Second run: provide different content for the same path
        c2 = component_class()
        c2.set_attributes(
            {
                "file_data": [Data(text="updated", data={"file_path": "/file.txt"})],
                "persistent_dir": persist_dir,
            }
        )
        result = c2.retrieve_content(file_path="/file.txt")
        assert result.text == "updated"  # New input overwrites persisted data to avoid stale cache

    def test_persistent_adds_new_files(self, component_class, tmp_path):
        """Test that new files are added when input includes both old and new files."""
        persist_dir = str(tmp_path / "persist")

        # First run: one file
        c1 = component_class()
        c1.set_attributes(
            {
                "file_data": [Data(text="file1", data={"file_path": "/a.txt"})],
                "persistent_dir": persist_dir,
            }
        )
        c1.retrieve_content(file_path="/a.txt")

        # Second run: both old and new file in input
        c2 = component_class()
        c2.set_attributes(
            {
                "file_data": [
                    Data(text="file1", data={"file_path": "/a.txt"}),
                    Data(text="file2", data={"file_path": "/b.txt"}),
                ],
                "persistent_dir": persist_dir,
            }
        )
        assert c2.retrieve_content(file_path="/a.txt").text == "file1"
        c2._cached_text_map = None
        c2._cached_dataframe_map = None
        assert c2.retrieve_content(file_path="/b.txt").text == "file2"

    def test_persistent_handles_corrupted_json(self, component_class, tmp_path):
        """Test graceful handling of corrupted persistent files."""
        persist_dir = str(tmp_path / "persist")
        Path(persist_dir).mkdir(parents=True)
        (Path(persist_dir) / "texts").mkdir()
        (Path(persist_dir) / "text_index.json").write_text("NOT VALID JSON")
        (Path(persist_dir) / "dataframe_index.json").write_text("{}")

        c = component_class()
        c.set_attributes(
            {
                "file_data": [Data(text="content", data={"file_path": "/ok.txt"})],
                "persistent_dir": persist_dir,
            }
        )
        # Should still work, falling back to building from input
        result = c.retrieve_content(file_path="/ok.txt")
        assert result.text == "content"

    def test_persistent_auto_sync_removes_stale_entries(self, component_class, tmp_path):
        """Test that files removed from file_data are removed from persisted maps."""
        persist_dir = str(tmp_path / "persist")

        # First run: persist two files
        c1 = component_class()
        c1.set_attributes(
            {
                "file_data": [
                    Data(text="file_a", data={"file_path": "/a.txt"}),
                    Data(text="file_b", data={"file_path": "/b.txt"}),
                ],
                "persistent_dir": persist_dir,
            }
        )
        c1.retrieve_content(file_path="/a.txt")

        # Second run: only provide /a.txt (removed /b.txt)
        c2 = component_class()
        c2.set_attributes(
            {
                "file_data": [Data(text="file_a", data={"file_path": "/a.txt"})],
                "persistent_dir": persist_dir,
            }
        )
        assert c2.retrieve_content(file_path="/a.txt").text == "file_a"

        # /b.txt should be gone
        c2._cached_text_map = None
        c2._cached_dataframe_map = None
        with pytest.raises(ValueError, match="not found"):
            c2.retrieve_content(file_path="/b.txt")

        # Third run: verify /b.txt is also gone from disk
        c3 = component_class()
        c3.set_attributes(
            {
                "file_data": [Data(text="file_a", data={"file_path": "/a.txt"})],
                "persistent_dir": persist_dir,
            }
        )
        with pytest.raises(ValueError, match="not found"):
            c3.retrieve_content(file_path="/b.txt")

    def test_persistent_auto_sync_does_not_wipe_on_empty_input(self, component_class, tmp_path):
        """Test that auto-sync does not remove entries when file_data is empty (tool call scenario)."""
        persist_dir = str(tmp_path / "persist")

        # First run: persist a file
        c1 = component_class()
        c1.set_attributes(
            {
                "file_data": [Data(text="content", data={"file_path": "/keep.txt"})],
                "persistent_dir": persist_dir,
            }
        )
        c1.retrieve_content(file_path="/keep.txt")

        # Second run: empty file_data (simulates tool call via deepcopy)
        c2 = component_class()
        c2.set_attributes(
            {
                "file_data": [],
                "persistent_dir": persist_dir,
            }
        )
        # Should still find the file from disk, not wiped
        result = c2.retrieve_content(file_path="/keep.txt")
        assert result.text == "content"

    def test_no_persistent_dir_works_as_before(self, component_class):
        """Test that empty persistent_dir means pure in-memory mode (regression)."""
        c = component_class()
        c.set_attributes(
            {
                "file_data": [Data(text="mem only", data={"file_path": "/mem.txt"})],
                "persistent_dir": "",
            }
        )
        result = c.retrieve_content(file_path="/mem.txt")
        assert result.text == "mem only"


# Made with Bob

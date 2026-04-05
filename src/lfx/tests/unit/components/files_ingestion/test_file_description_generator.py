"""Tests for FileDescriptionGeneratorComponent."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from lfx.components.files_ingestion.file_description_generator import FileDescriptionGeneratorComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class TestFileDescriptionGeneratorComponent:
    """Test cases for FileDescriptionGeneratorComponent."""

    def setup_method(self):
        """Set up test fixtures."""
        self.component = FileDescriptionGeneratorComponent()
        # Mock the LLM
        self.mock_llm = MagicMock()
        self.component.llm = self.mock_llm

    def test_extract_file_paths_from_dataframe_column(self):
        """Test extracting file paths from DataFrame with file_path column."""
        # Create a DataFrame with file_path column (simulating Read File output)
        df = DataFrame([
            {"file_path": "/path/to/file1.csv", "text": "content1"},
            {"file_path": "/path/to/file2.csv", "text": "content2"},
        ])

        self.component.file_data = [df]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        # Mock the subprocess to avoid actual execution
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='[{"text": "desc1", "file_path": "/path/to/file1.csv"}, {"text": "desc2", "file_path": "/path/to/file2.csv"}]',
                stderr="",
            )

            with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
                result = self.component.generate_descriptions()

        # Verify the subprocess was called with correct file paths
        call_args = mock_run.call_args
        import json
        config = json.loads(call_args[1]["input"])
        assert len(config["file_paths"]) == 2
        assert "/path/to/file1.csv" in config["file_paths"]
        assert "/path/to/file2.csv" in config["file_paths"]

        # Verify output
        assert len(result) == 2
        assert all(isinstance(item, Data) for item in result)
        assert result[0].data["text"] == "desc1"
        assert result[1].data["text"] == "desc2"

    def test_extract_file_paths_from_dataframe_attrs(self):
        """Test extracting file paths from DataFrame attrs (legacy support)."""
        # Create a DataFrame with attrs (legacy approach)
        df = DataFrame([{"text": "content"}])
        df.attrs["source_file_path"] = "/path/to/legacy_file.csv"

        self.component.file_data = [df]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='[{"text": "legacy desc", "file_path": "/path/to/legacy_file.csv"}]',
                stderr="",
            )

            with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
                result = self.component.generate_descriptions()

        # Verify the subprocess was called with correct file path
        call_args = mock_run.call_args
        import json
        config = json.loads(call_args[1]["input"])
        assert len(config["file_paths"]) == 1
        assert "/path/to/legacy_file.csv" in config["file_paths"]

    def test_extract_file_paths_from_data_objects(self):
        """Test extracting file paths from Data objects."""
        data1 = Data(data={"file_path": "/path/to/data1.txt", "text": "content1"})
        data2 = Data(data={"file_path": "/path/to/data2.txt", "text": "content2"})

        self.component.file_data = [data1, data2]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='[{"text": "desc1", "file_path": "/path/to/data1.txt"}, {"text": "desc2", "file_path": "/path/to/data2.txt"}]',
                stderr="",
            )

            with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
                result = self.component.generate_descriptions()

        # Verify output
        assert len(result) == 2
        assert result[0].data["file_path"] == "/path/to/data1.txt"
        assert result[1].data["file_path"] == "/path/to/data2.txt"

    def test_extract_unique_file_paths_from_dataframe(self):
        """Test that duplicate file paths in DataFrame are deduplicated."""
        # Create a DataFrame with duplicate file paths
        df = DataFrame([
            {"file_path": "/path/to/file1.csv", "text": "row1"},
            {"file_path": "/path/to/file1.csv", "text": "row2"},
            {"file_path": "/path/to/file2.csv", "text": "row3"},
        ])

        self.component.file_data = [df]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='[{"text": "desc1", "file_path": "/path/to/file1.csv"}, {"text": "desc2", "file_path": "/path/to/file2.csv"}]',
                stderr="",
            )

            with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
                result = self.component.generate_descriptions()

        # Verify only unique file paths were processed
        call_args = mock_run.call_args
        import json
        config = json.loads(call_args[1]["input"])
        assert len(config["file_paths"]) == 2

    def test_empty_dataframe_returns_empty_list(self):
        """Test that empty DataFrame returns empty list."""
        df = DataFrame()

        self.component.file_data = [df]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
            result = self.component.generate_descriptions()

        assert result == []

    def test_dataframe_without_file_path_returns_empty_list(self):
        """Test that DataFrame without file_path column or attrs returns empty list."""
        df = DataFrame([{"text": "content without path"}])

        self.component.file_data = [df]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
            result = self.component.generate_descriptions()

        assert result == []

    def test_mixed_input_types(self):
        """Test handling mixed input types (DataFrame and Data objects)."""
        df = DataFrame([{"file_path": "/path/to/file1.csv", "text": "content1"}])
        data = Data(data={"file_path": "/path/to/file2.txt", "text": "content2"})

        self.component.file_data = [df, data]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='[{"text": "desc1", "file_path": "/path/to/file1.csv"}, {"text": "desc2", "file_path": "/path/to/file2.txt"}]',
                stderr="",
            )

            with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
                result = self.component.generate_descriptions()

        # Verify both file paths were processed
        call_args = mock_run.call_args
        import json
        config = json.loads(call_args[1]["input"])
        assert len(config["file_paths"]) == 2

    def test_subprocess_failure_raises_error(self):
        """Test that subprocess failure raises RuntimeError."""
        df = DataFrame([{"file_path": "/path/to/file.csv", "text": "content"}])

        self.component.file_data = [df]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: Something went wrong",
            )

            with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
                with pytest.raises(RuntimeError, match="Ingestion subprocess failed"):
                    self.component.generate_descriptions()

    def test_invalid_json_output_raises_error(self):
        """Test that invalid JSON from subprocess raises RuntimeError."""
        df = DataFrame([{"file_path": "/path/to/file.csv", "text": "content"}])

        self.component.file_data = [df]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not valid json",
                stderr="",
            )

            with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
                with pytest.raises(RuntimeError, match="Invalid JSON from subprocess"):
                    self.component.generate_descriptions()

    def test_dataframe_with_nan_file_paths(self):
        """Test that NaN values in file_path column are filtered out."""
        df = DataFrame([
            {"file_path": "/path/to/file1.csv", "text": "content1"},
            {"file_path": None, "text": "content2"},
            {"file_path": "/path/to/file3.csv", "text": "content3"},
        ])

        self.component.file_data = [df]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='[{"text": "desc1", "file_path": "/path/to/file1.csv"}, {"text": "desc3", "file_path": "/path/to/file3.csv"}]',
                stderr="",
            )

            with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
                result = self.component.generate_descriptions()

        # Verify only non-NaN file paths were processed
        call_args = mock_run.call_args
        import json
        config = json.loads(call_args[1]["input"])
        assert len(config["file_paths"]) == 2
        assert None not in config["file_paths"]

    def test_one_description_per_file(self):
        """Test that component generates exactly one description per unique file."""
        # Simulate Read File output with 2 files
        df = DataFrame([
            {"file_path": "/path/to/file1.csv", "text": "ratings,title,text..."},
            {"file_path": "/path/to/file2.csv", "text": "listing_id,name,host_id..."},
        ])

        self.component.file_data = [df]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch("subprocess.run") as mock_run:
            # Simulate subprocess returning one description per file
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='[{"text": "This file contains hotel ratings data", "file_path": "/path/to/file1.csv"}, {"text": "This file contains listing information", "file_path": "/path/to/file2.csv"}]',
                stderr="",
            )

            with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
                result = self.component.generate_descriptions()

        # Verify exactly one description per file
        assert len(result) == 2
        assert result[0].data["file_path"] == "/path/to/file1.csv"
        assert result[0].data["text"] == "This file contains hotel ratings data"
        assert result[1].data["file_path"] == "/path/to/file2.csv"
        assert result[1].data["text"] == "This file contains listing information"

# Made with Bob

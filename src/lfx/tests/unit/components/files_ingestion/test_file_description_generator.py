"""Tests for FileDescriptionGeneratorComponent."""

import json
from unittest.mock import MagicMock, patch

import pytest
from lfx.components.files_ingestion.file_description_generator import FileDescriptionGeneratorComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


def _wrap_results(results_list):
    """Wrap a list of results in the expected subprocess output format."""
    return json.dumps({"results": results_list, "failed": [], "total": len(results_list)})


class TestFileDescriptionGeneratorComponent:
    """Test cases for FileDescriptionGeneratorComponent."""

    def setup_method(self):
        """Set up test fixtures."""
        self.component = FileDescriptionGeneratorComponent()
        # Mock the LLM
        self.mock_llm = MagicMock()
        self.component.llm = self.mock_llm

    @staticmethod
    def _make_mock_popen(stdout_data, returncode=0, stderr_data=""):
        """Create a mock Popen that simulates subprocess behavior."""
        import io

        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = io.StringIO(stdout_data)
        mock_proc.stderr = io.StringIO(stderr_data)
        mock_proc.returncode = returncode
        mock_proc.pid = 12345
        mock_proc.poll = MagicMock(return_value=returncode)
        mock_proc.wait = MagicMock(return_value=returncode)
        return mock_proc

    def test_extract_file_paths_from_dataframe_column(self):
        """Test extracting file paths from DataFrame with file_path column."""
        file_dataframe = DataFrame(
            [
                {"file_path": "/path/to/file1.csv", "text": "content1"},
                {"file_path": "/path/to/file2.csv", "text": "content2"},
            ]
        )

        self.component.file_data = [file_dataframe]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        results = [
            {"text": "desc1", "file_path": "/path/to/file1.csv"},
            {"text": "desc2", "file_path": "/path/to/file2.csv"},
        ]
        mock_proc = self._make_mock_popen(_wrap_results(results))

        with (
            patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}),
        ):
            result = self.component.generate_descriptions()

        assert mock_popen.called

        write_calls = mock_proc.stdin.write.call_args_list
        config = json.loads(write_calls[0][0][0])
        assert len(config["file_paths"]) == 2
        assert "/path/to/file1.csv" in config["file_paths"]
        assert "/path/to/file2.csv" in config["file_paths"]

        assert len(result) == 2
        assert all(isinstance(item, Data) for item in result)
        assert result[0].data["text"] == "desc1"
        assert result[1].data["text"] == "desc2"

    def test_extract_file_paths_from_dataframe_attrs(self):
        """Test extracting file paths from DataFrame attrs (legacy support)."""
        file_dataframe = DataFrame([{"text": "content"}])
        file_dataframe.attrs["source_file_path"] = "/path/to/legacy_file.csv"

        self.component.file_data = [file_dataframe]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        results = [{"text": "legacy desc", "file_path": "/path/to/legacy_file.csv"}]
        mock_proc = self._make_mock_popen(_wrap_results(results))

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}),
        ):
            _result = self.component.generate_descriptions()

        write_calls = mock_proc.stdin.write.call_args_list
        config = json.loads(write_calls[0][0][0])
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

        results = [
            {"text": "desc1", "file_path": "/path/to/data1.txt"},
            {"text": "desc2", "file_path": "/path/to/data2.txt"},
        ]
        mock_proc = self._make_mock_popen(_wrap_results(results))

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}),
        ):
            result = self.component.generate_descriptions()

        assert len(result) == 2
        assert result[0].data["file_path"] == "/path/to/data1.txt"
        assert result[1].data["file_path"] == "/path/to/data2.txt"

    def test_extract_unique_file_paths_from_dataframe(self):
        """Test that duplicate file paths in DataFrame are deduplicated."""
        file_dataframe = DataFrame(
            [
                {"file_path": "/path/to/file1.csv", "text": "row1"},
                {"file_path": "/path/to/file1.csv", "text": "row2"},
                {"file_path": "/path/to/file2.csv", "text": "row3"},
            ]
        )

        self.component.file_data = [file_dataframe]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        results = [
            {"text": "desc1", "file_path": "/path/to/file1.csv"},
            {"text": "desc2", "file_path": "/path/to/file2.csv"},
        ]
        mock_proc = self._make_mock_popen(_wrap_results(results))

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}),
        ):
            _result = self.component.generate_descriptions()

        write_calls = mock_proc.stdin.write.call_args_list
        config = json.loads(write_calls[0][0][0])
        assert len(config["file_paths"]) == 2

    def test_empty_dataframe_returns_empty_list(self):
        """Test that empty DataFrame returns empty list."""
        file_dataframe = DataFrame()

        self.component.file_data = [file_dataframe]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
            result = self.component.generate_descriptions()

        assert result == []

    def test_dataframe_without_file_path_returns_empty_list(self):
        """Test that DataFrame without file_path column or attrs returns empty list."""
        file_dataframe = DataFrame([{"text": "content without path"}])

        self.component.file_data = [file_dataframe]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        with patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}):
            result = self.component.generate_descriptions()

        assert result == []

    def test_mixed_input_types(self):
        """Test handling mixed input types (DataFrame and Data objects)."""
        file_dataframe = DataFrame([{"file_path": "/path/to/file1.csv", "text": "content1"}])
        data = Data(data={"file_path": "/path/to/file2.txt", "text": "content2"})

        self.component.file_data = [file_dataframe, data]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        results = [
            {"text": "desc1", "file_path": "/path/to/file1.csv"},
            {"text": "desc2", "file_path": "/path/to/file2.txt"},
        ]
        mock_proc = self._make_mock_popen(_wrap_results(results))

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}),
        ):
            _result = self.component.generate_descriptions()

        write_calls = mock_proc.stdin.write.call_args_list
        config = json.loads(write_calls[0][0][0])
        assert len(config["file_paths"]) == 2

    def test_subprocess_failure_raises_error(self):
        """Test that subprocess failure raises RuntimeError."""
        file_dataframe = DataFrame([{"file_path": "/path/to/file.csv", "text": "content"}])

        self.component.file_data = [file_dataframe]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        mock_proc = self._make_mock_popen("", returncode=1, stderr_data="Error: Something went wrong")

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}),
            pytest.raises(RuntimeError, match="Ingestion subprocess failed"),
        ):
            self.component.generate_descriptions()

    def test_invalid_json_output_raises_error(self):
        """Test that invalid JSON from subprocess raises RuntimeError."""
        file_dataframe = DataFrame([{"file_path": "/path/to/file.csv", "text": "content"}])

        self.component.file_data = [file_dataframe]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        mock_proc = self._make_mock_popen("not valid json")

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}),
            pytest.raises(RuntimeError, match="Invalid JSON from subprocess"),
        ):
            self.component.generate_descriptions()

    def test_dataframe_with_nan_file_paths(self):
        """Test that NaN values in file_path column are filtered out."""
        file_dataframe = DataFrame(
            [
                {"file_path": "/path/to/file1.csv", "text": "content1"},
                {"file_path": None, "text": "content2"},
                {"file_path": "/path/to/file3.csv", "text": "content3"},
            ]
        )

        self.component.file_data = [file_dataframe]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        results = [
            {"text": "desc1", "file_path": "/path/to/file1.csv"},
            {"text": "desc3", "file_path": "/path/to/file3.csv"},
        ]
        mock_proc = self._make_mock_popen(_wrap_results(results))

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}),
        ):
            _result = self.component.generate_descriptions()

        write_calls = mock_proc.stdin.write.call_args_list
        config = json.loads(write_calls[0][0][0])
        assert len(config["file_paths"]) == 2
        assert None not in config["file_paths"]

    def test_one_description_per_file(self):
        """Test that component generates exactly one description per unique file."""
        file_dataframe = DataFrame(
            [
                {"file_path": "/path/to/file1.csv", "text": "ratings,title,text..."},
                {"file_path": "/path/to/file2.csv", "text": "listing_id,name,host_id..."},
            ]
        )

        self.component.file_data = [file_dataframe]
        self.component.cache_dir = "./test_cache"
        self.component.embedding_model = "test-model"
        self.component.batch_size = 8

        results = [
            {"text": "This file contains hotel ratings data", "file_path": "/path/to/file1.csv"},
            {"text": "This file contains listing information", "file_path": "/path/to/file2.csv"},
        ]
        mock_proc = self._make_mock_popen(_wrap_results(results))

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch.object(self.component, "_serialize_llm", return_value={"__class_path__": "test.LLM"}),
        ):
            result = self.component.generate_descriptions()

        assert len(result) == 2
        assert result[0].data["file_path"] == "/path/to/file1.csv"
        assert result[0].data["text"] == "This file contains hotel ratings data"
        assert result[1].data["file_path"] == "/path/to/file2.csv"
        assert result[1].data["text"] == "This file contains listing information"

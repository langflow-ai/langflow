"""Tests for FileDescriptionGeneratorComponent.

Tests focus on critical logic and edge cases using mocks to avoid LLM and Docling dependencies:
- File path extraction from Data and DataFrame inputs
- Subprocess execution and error handling
- JSON parsing and result processing
- Edge cases with empty data, missing paths, and malformed responses
"""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from lfx.components.files_ingestion.file_description_generator import FileDescriptionGeneratorComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from tests.base import ComponentTestBaseWithoutClient


def _mock_popen(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Create a mock Popen context that replaces subprocess.Popen.

    Returns a (patcher, mock_proc) where patcher is used as a context manager.
    """
    mock_proc = Mock()
    mock_proc.stdin = Mock()
    mock_proc.stdout = StringIO(stdout)
    mock_proc.stderr = StringIO(stderr)
    mock_proc.returncode = returncode
    mock_proc.poll = Mock(return_value=returncode)  # process already finished
    mock_proc.wait = Mock(return_value=returncode)
    mock_proc.kill = Mock()
    patcher = patch("subprocess.Popen", return_value=mock_proc)
    return patcher, mock_proc


def _wrap_output(results: list, *, failed: list | None = None) -> dict:
    """Wrap subprocess results in the expected output format."""
    failed_items = []
    for f in failed or []:
        if isinstance(f, dict):
            failed_items.append(f)
        else:
            failed_items.append({"file_path": f, "error": "Test error"})
    return {"results": results, "failed": failed_items, "total": len(results) + len(failed_items)}


class TestFileDescriptionGeneratorComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return FileDescriptionGeneratorComponent

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM for testing."""
        llm = Mock()
        llm.__class__.__name__ = "MockLLM"
        llm.__class__.__module__ = "tests.mock"
        return llm

    @pytest.fixture
    def default_kwargs(self, mock_llm):
        """Return default kwargs with sample file data and mock LLM."""
        return {
            "file_data": [
                Data(text="content1", data={"file_path": "/path/to/file1.txt"}),
                Data(text="content2", data={"file_path": "/path/to/file2.txt"}),
            ],
            "llm": mock_llm,
            "cache_dir": "./test_cache",
            "embedding_model": "test-model",
            "batch_size": 8,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return empty list - new component without version history."""
        return []

    # ========== Core Functionality Tests ==========

    def test_generate_descriptions_basic_success(self, component_class, default_kwargs):
        """Test basic successful description generation with Data inputs."""
        component = component_class()
        component.set_attributes(default_kwargs)

        mock_output = [
            {"text": "Description of file1", "file_path": "/path/to/file1.txt"},
            {"text": "Description of file2", "file_path": "/path/to/file2.txt"},
        ]

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with _mock_popen(stdout=json.dumps(_wrap_output(mock_output)))[0]:
                result = component.generate_descriptions()

                assert len(result) == 2
                assert all(isinstance(item, Data) for item in result)
                assert result[0].data["text"] == "Description of file1"
                assert result[0].data["file_path"] == "/path/to/file1.txt"
                assert result[1].data["text"] == "Description of file2"
                assert result[1].data["file_path"] == "/path/to/file2.txt"

    def test_generate_descriptions_with_dataframe_input(self, component_class, mock_llm):
        """Test description generation with DataFrame inputs containing source_file_path."""
        df1 = DataFrame(pd.DataFrame({"col": [1]}))
        df1.attrs["source_file_path"] = "/path/to/data1.csv"

        df2 = DataFrame(pd.DataFrame({"col": [2]}))
        df2.attrs["source_file_path"] = "/path/to/data2.csv"

        component = component_class()
        component.set_attributes(
            {
                "file_data": [df1, df2],
                "llm": mock_llm,
                "cache_dir": "./test_cache",
                "embedding_model": "test-model",
                "batch_size": 8,
            }
        )

        mock_output = [
            {"text": "CSV description 1", "file_path": "/path/to/data1.csv"},
            {"text": "CSV description 2", "file_path": "/path/to/data2.csv"},
        ]

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with _mock_popen(stdout=json.dumps(_wrap_output(mock_output)))[0]:
                result = component.generate_descriptions()

                assert len(result) == 2
                assert result[0].data["file_path"] == "/path/to/data1.csv"
                assert result[1].data["file_path"] == "/path/to/data2.csv"

    def test_generate_descriptions_mixed_data_and_dataframe(self, component_class, mock_llm):
        """Test with mixed Data and DataFrame inputs."""
        df = DataFrame(pd.DataFrame({"col": [1]}))
        df.attrs["source_file_path"] = "/path/to/data.csv"

        data_obj = Data(text="text content", data={"file_path": "/path/to/file.txt"})

        component = component_class()
        component.set_attributes(
            {
                "file_data": [df, data_obj],
                "llm": mock_llm,
                "cache_dir": "./test_cache",
                "embedding_model": "test-model",
                "batch_size": 8,
            }
        )

        mock_output = [
            {"text": "CSV description", "file_path": "/path/to/data.csv"},
            {"text": "Text description", "file_path": "/path/to/file.txt"},
        ]

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with _mock_popen(stdout=json.dumps(_wrap_output(mock_output)))[0]:
                result = component.generate_descriptions()

                assert len(result) == 2

    # ========== Edge Cases & Error Handling ==========

    def test_generate_descriptions_empty_file_data(self, component_class, default_kwargs):
        """Test handling of empty file data list."""
        component = component_class()
        default_kwargs["file_data"] = []
        component.set_attributes(default_kwargs)

        result = component.generate_descriptions()

        assert result == []

    def test_generate_descriptions_data_without_file_path(self, component_class, mock_llm):
        """Test that Data objects without file_path are skipped."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="no path", data={}),
                    Data(text="has path", data={"file_path": "/path/to/valid.txt"}),
                ],
                "llm": mock_llm,
                "cache_dir": "./test_cache",
                "embedding_model": "test-model",
                "batch_size": 8,
            }
        )

        mock_output = [
            {"text": "Valid description", "file_path": "/path/to/valid.txt"},
        ]

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with _mock_popen(stdout=json.dumps(_wrap_output(mock_output)))[0]:
                result = component.generate_descriptions()

                assert len(result) == 1
                assert result[0].data["file_path"] == "/path/to/valid.txt"

    def test_generate_descriptions_dataframe_without_source_path(self, component_class, mock_llm):
        """Test that DataFrame without source_file_path is skipped."""
        df1 = DataFrame(pd.DataFrame({"col": [1]}))
        # No source_file_path set

        df2 = DataFrame(pd.DataFrame({"col": [2]}))
        df2.attrs["source_file_path"] = "/path/to/valid.csv"

        component = component_class()
        component.set_attributes(
            {
                "file_data": [df1, df2],
                "llm": mock_llm,
                "cache_dir": "./test_cache",
                "embedding_model": "test-model",
                "batch_size": 8,
            }
        )

        mock_output = [
            {"text": "Valid CSV description", "file_path": "/path/to/valid.csv"},
        ]

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with _mock_popen(stdout=json.dumps(_wrap_output(mock_output)))[0]:
                result = component.generate_descriptions()

                assert len(result) == 1
                assert result[0].data["file_path"] == "/path/to/valid.csv"

    def test_generate_descriptions_all_items_without_paths(self, component_class, mock_llm):
        """Test when all items lack file paths - should return empty list."""
        df = DataFrame(pd.DataFrame({"col": [1]}))
        # No source_file_path

        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="no path", data={}),
                    df,
                ],
                "llm": mock_llm,
                "cache_dir": "./test_cache",
                "embedding_model": "test-model",
                "batch_size": 8,
            }
        )

        result = component.generate_descriptions()

        assert result == []

    def test_generate_descriptions_unsupported_input_type(self, component_class, mock_llm):
        """Test handling of unsupported input types - should skip them."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    "not a Data or DataFrame object",
                    Data(text="valid", data={"file_path": "/path/to/file.txt"}),
                ],
                "llm": mock_llm,
                "cache_dir": "./test_cache",
                "embedding_model": "test-model",
                "batch_size": 8,
            }
        )

        mock_output = [
            {"text": "Description", "file_path": "/path/to/file.txt"},
        ]

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with _mock_popen(stdout=json.dumps(_wrap_output(mock_output)))[0]:
                result = component.generate_descriptions()

                # Should skip unsupported type and process valid Data
                assert len(result) == 1

    def test_generate_descriptions_subprocess_failure(self, component_class, default_kwargs):
        """Test handling of subprocess failure with non-zero exit code."""
        component = component_class()
        component.set_attributes(default_kwargs)

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with (
                _mock_popen(stderr="ERROR: Something went wrong in subprocess", returncode=1)[0],
                pytest.raises(RuntimeError, match="Ingestion subprocess failed"),
            ):
                component.generate_descriptions()

    def test_generate_descriptions_invalid_json_response(self, component_class, default_kwargs):
        """Test handling of invalid JSON from subprocess."""
        component = component_class()
        component.set_attributes(default_kwargs)

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with (
                _mock_popen(stdout="Not valid JSON {{")[0],
                pytest.raises(RuntimeError, match="Invalid JSON from subprocess"),
            ):
                component.generate_descriptions()

    def test_generate_descriptions_empty_json_array(self, component_class, default_kwargs):
        """Test that all files failing raises RuntimeError."""
        component = component_class()
        component.set_attributes(default_kwargs)

        empty_output = json.dumps(_wrap_output([], failed=["/path/to/file1.txt", "/path/to/file2.txt"]))

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with (
                _mock_popen(stdout=empty_output)[0],
                pytest.raises(RuntimeError, match="Ingestion failed"),
            ):
                component.generate_descriptions()

    def test_generate_descriptions_partial_success_raises(self, component_class, default_kwargs):
        """Test that partial success (some files failed) raises RuntimeError."""
        component = component_class()
        component.set_attributes(default_kwargs)

        partial_output = json.dumps(
            _wrap_output(
                [{"text": "Description of file1", "file_path": "/path/to/file1.txt"}],
                failed=["/path/to/file2.txt"],
            )
        )

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with (
                _mock_popen(stdout=partial_output, stderr="WARNING: file2.txt failed")[0],
                pytest.raises(RuntimeError, match="Ingestion failed"),
            ):
                component.generate_descriptions()

    def test_generate_descriptions_subprocess_timeout(self, component_class, default_kwargs):
        """Test handling of subprocess timeout."""
        default_kwargs["timeout"] = 1  # 1 second timeout
        component = component_class()
        component.set_attributes(default_kwargs)

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            # Create a Popen mock that never finishes (poll always returns None)
            mock_proc = Mock()
            mock_proc.stdin = Mock()
            mock_proc.stdout = StringIO("")
            mock_proc.stderr = StringIO("")
            mock_proc.poll = Mock(return_value=None)  # never finishes
            mock_proc.kill = Mock()
            mock_proc.wait = Mock()

            with patch("subprocess.Popen", return_value=mock_proc), pytest.raises(TimeoutError, match="timed out"):
                component.generate_descriptions()

    def test_generate_descriptions_path_normalization(self, component_class, mock_llm):
        """Test that file paths are normalized using Path (important for cross-platform compatibility)."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="content", data={"file_path": "relative/path/file.txt"}),
                ],
                "llm": mock_llm,
                "cache_dir": "./test_cache",
                "embedding_model": "test-model",
                "batch_size": 8,
            }
        )

        mock_output = [
            {"text": "Description", "file_path": str(Path("relative/path/file.txt"))},
        ]

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            patcher, mock_proc = _mock_popen(stdout=json.dumps(_wrap_output(mock_output)))
            with patcher:
                component.generate_descriptions()

                # Verify path was normalized — config is written to stdin
                stdin_write_call = mock_proc.stdin.write.call_args[0][0]
                config = json.loads(stdin_write_call)
                assert config["file_paths"][0] == str(Path("relative/path/file.txt"))

    def test_generate_descriptions_result_data_structure(self, component_class, default_kwargs):
        """Test that result Data objects have correct structure with text and file_path keys."""
        component = component_class()
        component.set_attributes(default_kwargs)

        mock_output = [
            {"text": "Test description", "file_path": "/path/to/file.txt"},
        ]

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with _mock_popen(stdout=json.dumps(_wrap_output(mock_output)))[0]:
                result = component.generate_descriptions()

                assert len(result) == 1
                assert isinstance(result[0], Data)
                assert "text" in result[0].data
                assert "file_path" in result[0].data
                assert result[0].data["text"] == "Test description"
                assert result[0].data["file_path"] == "/path/to/file.txt"

    def test_generate_descriptions_duplicate_file_paths(self, component_class, mock_llm):
        """Test handling of duplicate file paths in input — subprocess deduplicates results."""
        component = component_class()
        component.set_attributes(
            {
                "file_data": [
                    Data(text="content1", data={"file_path": "/path/to/file.txt"}),
                    Data(text="content2", data={"file_path": "/path/to/file.txt"}),
                    Data(text="content3", data={"file_path": "/path/to/other.txt"}),
                ],
                "llm": mock_llm,
                "cache_dir": "./test_cache",
                "embedding_model": "test-model",
                "batch_size": 8,
            }
        )

        # Component sends all paths; subprocess returns one description per unique file
        mock_output = [
            {"text": "Description", "file_path": "/path/to/file.txt"},
            {"text": "Other description", "file_path": "/path/to/other.txt"},
        ]

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            patcher, mock_proc = _mock_popen(stdout=json.dumps(_wrap_output(mock_output)))
            with patcher:
                result = component.generate_descriptions()

                # Verify all paths were sent (dedup is subprocess's responsibility)
                stdin_write_call = mock_proc.stdin.write.call_args[0][0]
                config = json.loads(stdin_write_call)
                assert len(config["file_paths"]) == 3
                # Verify results contain one description per unique file
                assert len(result) == 2
                assert result[0].data["file_path"] == "/path/to/file.txt"
                assert result[1].data["file_path"] == "/path/to/other.txt"

    def test_generate_descriptions_llm_serialization_failure(self, component_class, default_kwargs):
        """Test handling of LLM serialization failure."""
        component = component_class()
        component.set_attributes(default_kwargs)

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.side_effect = ValueError("Cannot serialize this LLM type")

            with pytest.raises(ValueError, match="Cannot serialize this LLM type"):
                component.generate_descriptions()

    def test_generate_descriptions_missing_text_key_in_output(self, component_class, default_kwargs):
        """Test handling of subprocess output missing 'text' key - should raise KeyError."""
        component = component_class()
        component.set_attributes(default_kwargs)

        # Output missing "text" key
        mock_output = [
            {"file_path": "/path/to/file.txt"},  # Missing "text"
        ]

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with _mock_popen(stdout=json.dumps(_wrap_output(mock_output)))[0], pytest.raises(KeyError, match="text"):
                component.generate_descriptions()

    def test_generate_descriptions_missing_file_path_key_in_output(self, component_class, default_kwargs):
        """Test handling of subprocess output missing 'file_path' key - should raise KeyError."""
        component = component_class()
        component.set_attributes(default_kwargs)

        # Output missing "file_path" key
        mock_output = [
            {"text": "Description"},  # Missing "file_path"
        ]

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            mock_serialize.return_value = {"__class_path__": "test.MockLLM"}

            with (
                _mock_popen(stdout=json.dumps(_wrap_output(mock_output)))[0],
                pytest.raises(KeyError, match="file_path"),
            ):
                component.generate_descriptions()

    def test_generate_descriptions_exception_propagation(self, component_class, default_kwargs):
        """Test that exceptions are properly propagated with debug logging."""
        component = component_class()
        component.set_attributes(default_kwargs)

        with patch("lfx.base.data.docling_utils._serialize_pydantic_model") as mock_serialize:
            # Simulate an unexpected exception
            mock_serialize.side_effect = RuntimeError("Unexpected error during serialization")

            with pytest.raises(RuntimeError, match="Unexpected error during serialization"):
                component.generate_descriptions()


# Made with Bob

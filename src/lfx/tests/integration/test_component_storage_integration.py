"""Integration tests for components using storage services.

These tests verify that components correctly use the storage abstraction layer
to read files from both local and S3 storage.
"""

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from lfx.base.data.utils import parse_pdf_to_text, parse_text_file_to_data, read_docx_file, read_text_file
from lfx.services.storage.local import LocalStorageService


class TestComponentStorageIntegration:
    """Test components work correctly with storage services."""

    @pytest.fixture
    def real_storage_service(self, tmp_path):
        """Create a real LocalStorageService."""
        return LocalStorageService(data_dir=tmp_path)

    @pytest.fixture
    def sample_text_file(self):
        """Sample text file content."""
        return b"This is a test text file.\nIt has multiple lines.\nFor testing purposes."

    @pytest.fixture
    def sample_csv_data(self):
        """Sample CSV content."""
        return b"name,age,city\nAlice,30,NYC\nBob,25,SF\nCarol,35,LA"

    @pytest.fixture
    def sample_json_data(self):
        """Sample JSON content."""
        return b'{"name": "Test", "value": 42, "items": ["a", "b", "c"]}'

    # Tests for read_text_file utility
    def test_read_text_file_local_storage(self, real_storage_service, sample_text_file, tmp_path):
        """Test read_text_file works with local storage."""
        import asyncio

        # Create file through storage service
        asyncio.run(real_storage_service.save_file("test-flow", "sample.txt", sample_text_file))
        file_path = real_storage_service.build_full_path("test-flow", "sample.txt")

        # Read through utility
        with patch("lfx.base.data.utils.get_storage_service", return_value=real_storage_service):
            content = read_text_file(file_path)

        assert "This is a test text file" in content
        assert "multiple lines" in content

    def test_read_text_file_direct_path(self, tmp_path, sample_text_file):
        """Test read_text_file works with direct file path (no storage service)."""
        # Create file directly
        test_file = tmp_path / "direct.txt"
        test_file.write_bytes(sample_text_file)

        # Read without storage service
        with patch("lfx.base.data.utils.get_storage_service", return_value=None):
            content = read_text_file(str(test_file))

        assert "This is a test text file" in content

    # Tests for parse_text_file_to_data utility
    def test_parse_text_file_to_data_json(self, real_storage_service, sample_json_data):
        """Test parsing JSON file through storage."""
        import asyncio

        # Create JSON file
        asyncio.run(real_storage_service.save_file("json-flow", "data.json", sample_json_data))
        file_path = real_storage_service.build_full_path("json-flow", "data.json")

        # Parse through utility
        with patch("lfx.base.data.utils.get_storage_service", return_value=real_storage_service):
            data = parse_text_file_to_data(file_path, silent_errors=False)

        assert data is not None
        assert "file_path" in data.data
        assert "text" in data.data

    def test_parse_text_file_to_data_yaml(self, real_storage_service):
        """Test parsing YAML file through storage."""
        import asyncio

        yaml_content = b"name: Test\nvalue: 42\nitems:\n  - a\n  - b\n  - c"

        # Create YAML file
        asyncio.run(real_storage_service.save_file("yaml-flow", "config.yaml", yaml_content))
        file_path = real_storage_service.build_full_path("yaml-flow", "config.yaml")

        # Parse through utility
        with patch("lfx.base.data.utils.get_storage_service", return_value=real_storage_service):
            data = parse_text_file_to_data(file_path, silent_errors=False)

        assert data is not None
        # YAML is parsed into dict
        assert data.data.get("text") is not None

    # Tests for BaseFileComponent structured loading
    def test_load_csv_through_storage(self, real_storage_service, sample_csv_data):
        """Test loading CSV through storage service."""
        import asyncio
        from lfx.base.data.base_file import BaseFileComponent

        # Create CSV file
        asyncio.run(real_storage_service.save_file("csv-flow", "data.csv", sample_csv_data))
        file_path = real_storage_service.build_full_path("csv-flow", "data.csv")

        # Create component instance (mock minimal requirements)
        component = BaseFileComponent.__new__(BaseFileComponent)

        # Load through helper
        with patch("lfx.base.data.base_file.get_storage_service", return_value=real_storage_service):
            result = component.load_files_structured_helper(file_path)

        assert result is not None
        assert len(result) == 3  # 3 rows
        assert result[0]["name"] == "Alice"
        assert result[1]["age"] == 25

    def test_load_excel_through_storage(self, real_storage_service, tmp_path):
        """Test loading Excel file through storage service."""
        import asyncio
        from lfx.base.data.base_file import BaseFileComponent

        # Create Excel file using pandas
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        excel_path = tmp_path / "temp.xlsx"
        df.to_excel(excel_path, index=False)
        excel_data = excel_path.read_bytes()

        # Save through storage service
        asyncio.run(real_storage_service.save_file("excel-flow", "data.xlsx", excel_data))
        file_path = real_storage_service.build_full_path("excel-flow", "data.xlsx")

        # Create component
        component = BaseFileComponent.__new__(BaseFileComponent)

        # Load through helper
        with patch("lfx.base.data.base_file.get_storage_service", return_value=real_storage_service):
            result = component.load_files_structured_helper(file_path)

        assert result is not None
        assert len(result) == 3
        assert result[0]["col1"] == 1
        assert result[2]["col2"] == "c"

    def test_load_parquet_through_storage(self, real_storage_service, tmp_path):
        """Test loading Parquet file through storage service."""
        import asyncio
        from lfx.base.data.base_file import BaseFileComponent

        # Create Parquet file
        df = pd.DataFrame({"nums": [10, 20, 30], "text": ["x", "y", "z"]})
        parquet_path = tmp_path / "temp.parquet"
        df.to_parquet(parquet_path, index=False)
        parquet_data = parquet_path.read_bytes()

        # Save through storage service
        asyncio.run(real_storage_service.save_file("parquet-flow", "data.parquet", parquet_data))
        file_path = real_storage_service.build_full_path("parquet-flow", "data.parquet")

        # Create component
        component = BaseFileComponent.__new__(BaseFileComponent)

        # Load through helper
        with patch("lfx.base.data.base_file.get_storage_service", return_value=real_storage_service):
            result = component.load_files_structured_helper(file_path)

        assert result is not None
        assert len(result) == 3
        assert result[0]["nums"] == 10

    # Tests for S3 path handling (with mocked S3)
    def test_s3_path_recognized_and_handled(self):
        """Test that S3 paths are properly recognized and routed to S3 storage."""
        from lfx.utils.storage_file_io import is_remote_path

        # Mock S3 storage service
        mock_s3_service = MagicMock()
        mock_s3_service.is_remote_path = MagicMock(return_value=True)

        with patch("lfx.utils.storage_file_io.get_storage_service", return_value=mock_s3_service):
            result = is_remote_path("s3://bucket/prefix/flow/file.txt")

        assert result is True
        mock_s3_service.is_remote_path.assert_called_once()

    # Integration test: Complete file processing workflow
    def test_complete_component_workflow(self, real_storage_service, sample_csv_data):
        """Test complete workflow: save → load → process."""
        import asyncio
        from lfx.base.data.base_file import BaseFileComponent

        # 1. Save file through storage service
        asyncio.run(real_storage_service.save_file("workflow", "sales.csv", sample_csv_data))

        # 2. Get path
        file_path = real_storage_service.build_full_path("workflow", "sales.csv")

        # 3. Verify it exists
        assert asyncio.run(real_storage_service.path_exists("workflow", "sales.csv"))

        # 4. Load through component
        component = BaseFileComponent.__new__(BaseFileComponent)
        with patch("lfx.base.data.base_file.get_storage_service", return_value=real_storage_service):
            result = component.load_files_structured_helper(file_path)

        # 5. Verify data
        assert result is not None
        assert len(result) == 3
        assert all("name" in row for row in result)
        assert all("age" in row for row in result)

    def test_unsupported_file_format_returns_none(self, real_storage_service):
        """Test that unsupported file formats return None gracefully."""
        import asyncio
        from lfx.base.data.base_file import BaseFileComponent

        # Create unsupported file
        asyncio.run(real_storage_service.save_file("test", "data.zip", b"fake zip content"))
        file_path = real_storage_service.build_full_path("test", "data.zip")

        component = BaseFileComponent.__new__(BaseFileComponent)
        with patch("lfx.base.data.base_file.get_storage_service", return_value=real_storage_service):
            result = component.load_files_structured_helper(file_path)

        assert result is None

    # Error handling tests
    def test_read_nonexistent_file_raises_error(self, real_storage_service):
        """Test that reading non-existent file raises appropriate error."""
        from lfx.base.data.utils import read_text_file

        file_path = real_storage_service.build_full_path("noflow", "nofile.txt")

        with patch("lfx.base.data.utils.get_storage_service", return_value=real_storage_service):
            with pytest.raises(FileNotFoundError):
                read_text_file(file_path)

    def test_parse_corrupted_json_handles_error(self, real_storage_service):
        """Test that corrupted JSON is handled with silent_errors."""
        import asyncio
        from lfx.base.data.utils import parse_text_file_to_data

        # Create corrupted JSON
        bad_json = b'{"incomplete": '
        asyncio.run(real_storage_service.save_file("bad", "corrupt.json", bad_json))
        file_path = real_storage_service.build_full_path("bad", "corrupt.json")

        with patch("lfx.base.data.utils.get_storage_service", return_value=real_storage_service):
            # With silent_errors=True, should return None
            result = parse_text_file_to_data(file_path, silent_errors=True)
            assert result is None

            # With silent_errors=False, should raise
            with pytest.raises(ValueError):
                parse_text_file_to_data(file_path, silent_errors=False)

    # Tests for storage-agnostic behavior
    def test_same_code_works_local_and_s3(self, real_storage_service):
        """Verify same code path works for both local and S3 (mocked)."""
        import asyncio
        from lfx.base.data.utils import read_text_file

        # Test with local storage
        sample_text = b"Storage agnostic content"
        asyncio.run(real_storage_service.save_file("agnostic", "test.txt", sample_text))
        local_path = real_storage_service.build_full_path("agnostic", "test.txt")

        with patch("lfx.base.data.utils.get_storage_service", return_value=real_storage_service):
            content_local = read_text_file(local_path)

        assert "Storage agnostic" in content_local

        # Mock S3 storage service
        mock_s3 = MagicMock()
        mock_s3.is_remote_path = MagicMock(return_value=True)
        mock_s3.parse_path = MagicMock(return_value=("flow", "test.txt"))
        mock_s3.read_file = MagicMock(return_value=sample_text)

        with patch("lfx.base.data.utils.get_storage_service", return_value=mock_s3):
            # Same function call, different storage backend
            content_s3 = read_text_file("s3://bucket/prefix/flow/test.txt")

        # Both should return same content
        assert content_local == content_s3

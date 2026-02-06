"""Tests for parameter handler table load_from_db functionality."""

from unittest.mock import MagicMock

import pytest
from lfx.graph.vertex.param_handler import ParameterHandler
from lfx.schema.table import Column


class TestParameterHandlerTableLoadFromDb:
    """Tests for table load_from_db functionality in ParameterHandler."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock vertex
        self.mock_vertex = MagicMock()
        self.mock_vertex.data = {
            "node": {
                "template": {
                    "table_field": {
                        "type": "table",
                        "table_schema": [
                            Column(name="username", load_from_db=True, default="admin"),
                            Column(name="email", load_from_db=True, default="user@example.com"),
                            Column(name="role", load_from_db=False, default="user"),
                            Column(name="active", load_from_db=False, default=True),
                        ],
                    }
                }
            }
        }

        # Create parameter handler
        self.handler = ParameterHandler(self.mock_vertex, storage_service=None)

    def test_handle_table_field_with_load_from_db_columns(self):
        """Test _handle_table_field identifies load_from_db columns correctly."""
        # Test data
        table_data = [
            {"username": "ADMIN_USER", "email": "ADMIN_EMAIL", "role": "admin", "active": True},
            {"username": "USER1", "email": "USER1_EMAIL", "role": "user", "active": False},
        ]

        params = {}

        # Call the method
        result_params = self.handler._handle_table_field("table_field", table_data, params)

        # Check that table data is preserved
        assert result_params["table_field"] == table_data

        # Check that load_from_db columns are identified
        assert "table_field_load_from_db_columns" in result_params
        load_from_db_columns = result_params["table_field_load_from_db_columns"]
        assert set(load_from_db_columns) == {"username", "email"}

        # Check that table field is added to load_from_db_fields
        assert "table:table_field" in self.handler.load_from_db_fields

    def test_handle_table_field_with_no_load_from_db_columns(self):
        """Test _handle_table_field when no columns have load_from_db=True."""
        # Update template to have no load_from_db columns
        self.mock_vertex.data["node"]["template"]["table_field"]["table_schema"] = [
            Column(name="field1", load_from_db=False, default="value1"),
            Column(name="field2", load_from_db=False, default="value2"),
        ]

        # Recreate handler with updated template
        self.handler = ParameterHandler(self.mock_vertex, storage_service=None)

        table_data = [{"field1": "val1", "field2": "val2"}]
        params = {}

        # Call the method
        result_params = self.handler._handle_table_field("table_field", table_data, params)

        # Check that table data is preserved
        assert result_params["table_field"] == table_data

        # Check that no metadata is added
        assert "table_field_load_from_db_columns" not in result_params
        assert "table:table_field" not in self.handler.load_from_db_fields

    def test_handle_table_field_with_dict_schema(self):
        """Test _handle_table_field with dictionary-based schema."""
        # Update template to use dict schema instead of Column objects
        self.mock_vertex.data["node"]["template"]["table_field"]["table_schema"] = [
            {"name": "api_key", "load_from_db": True},
            {"name": "timeout", "load_from_db": False},
        ]

        # Recreate handler with updated template
        self.handler = ParameterHandler(self.mock_vertex, storage_service=None)

        table_data = [{"api_key": "MY_API_KEY", "timeout": 30}]  # pragma: allowlist secret
        params = {}

        # Call the method
        result_params = self.handler._handle_table_field("table_field", table_data, params)

        # Check that load_from_db columns are identified correctly
        load_from_db_columns = result_params["table_field_load_from_db_columns"]
        assert load_from_db_columns == ["api_key"]
        assert "table:table_field" in self.handler.load_from_db_fields

    def test_handle_table_field_with_none_value(self):
        """Test _handle_table_field with None table value."""
        params = {}

        # Call the method with None
        result_params = self.handler._handle_table_field("table_field", None, params)

        # Should return empty list
        assert result_params["table_field"] == []

        # Should not add any metadata since no schema processing occurs
        assert "table_field_load_from_db_columns" not in result_params
        assert "table:table_field" not in self.handler.load_from_db_fields

    def test_handle_table_field_with_invalid_data_type(self):
        """Test _handle_table_field with invalid data type raises ValueError."""
        params = {}

        # Test with string (invalid for table)
        with pytest.raises(ValueError, match=r"Invalid value type.*for table field"):
            self.handler._handle_table_field("table_field", "invalid_data", params)

        # Test with list of non-dicts (invalid for table)
        with pytest.raises(ValueError, match=r"Invalid value type.*for table field"):
            self.handler._handle_table_field("table_field", ["string1", "string2"], params)

    def test_handle_table_field_with_empty_table_schema(self):
        """Test _handle_table_field when table_schema is empty."""
        # Update template to have empty schema
        self.mock_vertex.data["node"]["template"]["table_field"]["table_schema"] = []

        # Recreate handler with updated template
        self.handler = ParameterHandler(self.mock_vertex, storage_service=None)

        table_data = [{"field1": "value1"}]
        params = {}

        # Call the method
        result_params = self.handler._handle_table_field("table_field", table_data, params)

        # Should preserve table data but not add metadata
        assert result_params["table_field"] == table_data
        assert "table_field_load_from_db_columns" not in result_params
        assert "table:table_field" not in self.handler.load_from_db_fields

    def test_handle_table_field_with_missing_table_schema(self):
        """Test _handle_table_field when table_schema key is missing."""
        # Update template to not have table_schema
        self.mock_vertex.data["node"]["template"]["table_field"] = {"type": "table"}

        # Recreate handler with updated template
        self.handler = ParameterHandler(self.mock_vertex, storage_service=None)

        table_data = [{"field1": "value1"}]
        params = {}

        # Call the method
        result_params = self.handler._handle_table_field("table_field", table_data, params)

        # Should preserve table data but not add metadata
        assert result_params["table_field"] == table_data
        assert "table_field_load_from_db_columns" not in result_params
        assert "table:table_field" not in self.handler.load_from_db_fields

    def test_handle_table_field_with_mixed_schema_types(self):
        """Test _handle_table_field with mixed Column objects and dicts."""
        # Update template to have mixed schema types
        self.mock_vertex.data["node"]["template"]["table_field"]["table_schema"] = [
            Column(name="col1", load_from_db=True),  # Column object
            {"name": "col2", "load_from_db": True},  # Dict
            Column(name="col3", load_from_db=False),  # Column object
            {"name": "col4", "load_from_db": False},  # Dict
        ]

        # Recreate handler with updated template
        self.handler = ParameterHandler(self.mock_vertex, storage_service=None)

        table_data = [{"col1": "val1", "col2": "val2", "col3": "val3", "col4": "val4"}]
        params = {}

        # Call the method
        result_params = self.handler._handle_table_field("table_field", table_data, params)

        # Should identify both types of load_from_db columns
        load_from_db_columns = result_params["table_field_load_from_db_columns"]

        assert set(load_from_db_columns) == {"col1", "col2"}
        assert "table:table_field" in self.handler.load_from_db_fields


class TestResolveFileWithFallback:
    """Tests for file path resolution with fallback."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock vertex with graph context
        self.mock_vertex = MagicMock()
        self.mock_vertex.data = {"node": {"template": {}}}
        self.mock_vertex.graph = MagicMock()
        self.mock_vertex.graph.context = {}

        # Create mock storage service
        self.mock_storage = MagicMock()

        # Create parameter handler
        self.handler = ParameterHandler(self.mock_vertex, storage_service=self.mock_storage)

    def test_resolve_file_storage_service_path_exists(self, tmp_path):
        """Test resolution when storage service returns existing file."""
        # Create a temp file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Mock storage service to return the temp file path
        self.mock_storage.resolve_component_path.return_value = str(test_file)

        result = self.handler._resolve_file_with_fallback("flow_id/test.txt")

        assert result == str(test_file)
        self.mock_storage.resolve_component_path.assert_called_once_with("flow_id/test.txt")

    def test_resolve_file_fallback_to_files_dir(self, tmp_path):
        """Test fallback to files_dir when storage path doesn't exist."""
        # Create a file in the files_dir
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        test_file = files_dir / "myfile.txt"
        test_file.write_text("test content")

        # Mock storage service to return non-existent path
        self.mock_storage.resolve_component_path.return_value = "/nonexistent/path/myfile.txt"

        # Set files_dir in context
        self.mock_vertex.graph.context = {"files_dir": str(files_dir)}

        result = self.handler._resolve_file_with_fallback("flow_id/myfile.txt")

        assert result == str(test_file)

    def test_resolve_file_fallback_to_project_path(self, tmp_path):
        """Test fallback to project_path when storage path and files_dir don't have the file."""
        # Create a file in the project_path
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        test_file = project_dir / "data.csv"
        test_file.write_text("a,b,c")

        # Mock storage service to return non-existent path
        self.mock_storage.resolve_component_path.return_value = "/nonexistent/path/data.csv"

        # Set project_path in context (no files_dir)
        self.mock_vertex.graph.context = {"project_path": str(project_dir)}

        result = self.handler._resolve_file_with_fallback("flow_id/data.csv")

        assert result == str(test_file)

    def test_resolve_file_files_dir_has_priority_over_project_path(self, tmp_path):
        """Test that files_dir is checked before project_path."""
        # Create files in both directories
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        files_file = files_dir / "config.json"
        files_file.write_text('{"source": "files_dir"}')

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_file = project_dir / "config.json"
        project_file.write_text('{"source": "project_dir"}')

        # Mock storage service to return non-existent path
        self.mock_storage.resolve_component_path.return_value = "/nonexistent/config.json"

        # Set both directories in context
        self.mock_vertex.graph.context = {
            "files_dir": str(files_dir),
            "project_path": str(project_dir),
        }

        result = self.handler._resolve_file_with_fallback("flow_id/config.json")

        # Should use files_dir (priority 1)
        assert result == str(files_file)

    def test_resolve_file_no_storage_service(self, tmp_path):
        """Test resolution when storage service is None."""
        # Create handler without storage service
        handler = ParameterHandler(self.mock_vertex, storage_service=None)

        # Create a file in the project_path
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        test_file = project_dir / "data.txt"
        test_file.write_text("content")

        # Set project_path in context
        self.mock_vertex.graph.context = {"project_path": str(project_dir)}

        result = handler._resolve_file_with_fallback("flow_id/data.txt")

        assert result == str(test_file)

    def test_resolve_file_returns_original_when_no_fallback_found(self):
        """Test that original resolved path is returned when no fallback exists."""
        # Mock storage service to return non-existent path
        self.mock_storage.resolve_component_path.return_value = "/nonexistent/path/missing.txt"

        # No context directories set
        self.mock_vertex.graph.context = {}

        result = self.handler._resolve_file_with_fallback("flow_id/missing.txt")

        # Should return the original resolved path
        assert result == "/nonexistent/path/missing.txt"

    def test_resolve_file_extracts_filename_from_logical_path(self, tmp_path):
        """Test that filename is correctly extracted from logical path."""
        # Create a file in the files_dir
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        test_file = files_dir / "document.pdf"
        test_file.write_text("PDF content")

        # Mock storage service to return non-existent path
        self.mock_storage.resolve_component_path.return_value = "/storage/uuid-123/document.pdf"

        # Set files_dir in context
        self.mock_vertex.graph.context = {"files_dir": str(files_dir)}

        # Test with nested logical path
        result = self.handler._resolve_file_with_fallback("flow_id/subdir/document.pdf")

        assert result == str(test_file)

    def test_resolve_file_handles_absolute_path(self, tmp_path):
        """Test handling of absolute paths that exist."""
        # Create an absolute path file
        test_file = tmp_path / "absolute.txt"
        test_file.write_text("absolute content")

        # Pass absolute path (no flow_id prefix)
        self.mock_storage.resolve_component_path.return_value = str(test_file)

        result = self.handler._resolve_file_with_fallback(str(test_file))

        assert result == str(test_file)

    def test_resolve_file_no_graph_context(self):
        """Test resolution when vertex has no graph."""
        # Create handler with vertex that has no graph
        mock_vertex = MagicMock()
        mock_vertex.data = {"node": {"template": {}}}
        mock_vertex.graph = None

        handler = ParameterHandler(mock_vertex, storage_service=self.mock_storage)

        # Mock storage service to return non-existent path
        self.mock_storage.resolve_component_path.return_value = "/nonexistent/file.txt"

        result = handler._resolve_file_with_fallback("flow_id/file.txt")

        # Should return the original resolved path (no fallback possible)
        assert result == "/nonexistent/file.txt"

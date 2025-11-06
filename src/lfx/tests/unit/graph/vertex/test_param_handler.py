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

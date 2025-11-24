from lfx.schema.data import Data
from lfx.schema.table import Column

from .table_schema_demo_component import TableSchemaDemoComponent


class TestTableSchemaDemoComponent:
    """Tests for TableSchemaDemoComponent that demonstrates table columns with load_from_db functionality."""

    def test_component_initialization(self):
        """Test that TableSchemaDemoComponent initializes correctly."""
        component = TableSchemaDemoComponent()

        assert component.display_name == "Table Schema Demo"
        assert component.name == "TableSchemaDemo"
        assert len(component.inputs) == 1
        assert len(component.outputs) == 2

        # Check that the table input has the expected schema
        table_input = component.inputs[0]
        assert table_input.name == "table_data"
        assert hasattr(table_input, "table_schema")

    def test_table_schema_configuration(self):
        """Test that the table schema is properly configured with load_from_db columns."""
        component = TableSchemaDemoComponent()
        table_input = component.inputs[0]

        # Verify schema exists and has expected columns
        assert table_input.table_schema is not None
        assert len(table_input.table_schema) == 4

        # Check each column's load_from_db setting
        schema_columns = table_input.table_schema
        assert schema_columns[0].load_from_db is True  # username
        assert schema_columns[1].load_from_db is True  # email
        assert schema_columns[2].load_from_db is False  # role
        assert schema_columns[3].load_from_db is False  # active

    def test_load_table_data_with_dict_rows(self):
        """Test loading table data when rows are dictionaries."""
        component = TableSchemaDemoComponent()
        component.table_data = [
            {"username": "admin", "email": "admin@example.com", "role": "admin", "active": True},
            {"username": "user1", "email": "user1@example.com", "role": "user", "active": True},
        ]

        result = component.load_table_data()

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, Data) for item in result)

        # Check the data content
        assert result[0].data["username"] == "admin"
        assert result[0].data["email"] == "admin@example.com"
        assert result[1].data["username"] == "user1"
        assert result[1].data["email"] == "user1@example.com"

    def test_load_table_data_with_data_objects(self):
        """Test loading table data when rows are already Data objects."""
        component = TableSchemaDemoComponent()
        data_rows = [
            Data(data={"username": "admin", "email": "admin@example.com"}),
            Data(data={"username": "user1", "email": "user1@example.com"}),
        ]
        component.table_data = data_rows

        result = component.load_table_data()

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, Data) for item in result)
        assert result[0] == data_rows[0]
        assert result[1] == data_rows[1]

    def test_load_table_data_with_mixed_types(self):
        """Test loading table data with mixed types (string, etc.)."""
        component = TableSchemaDemoComponent()
        component.table_data = [{"username": "admin"}, "user_string", 123]

        result = component.load_table_data()

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(item, Data) for item in result)

        # First item should be a dict
        assert result[0].data["username"] == "admin"

        # Second item should be converted to Data with row/index
        assert result[1].data["row"] == "user_string"
        assert result[1].data["index"] == 1

        # Third item should be converted to Data with row/index
        assert result[2].data["row"] == "123"
        assert result[2].data["index"] == 2

    def test_load_table_data_empty(self):
        """Test loading empty table data."""
        component = TableSchemaDemoComponent()
        component.table_data = []

        result = component.load_table_data()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_load_table_data_none(self):
        """Test loading when table_data is None."""
        component = TableSchemaDemoComponent()
        component.table_data = None

        result = component.load_table_data()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_schema_info(self):
        """Test getting schema information about load_from_db columns."""
        component = TableSchemaDemoComponent()

        # The get_schema_info method should return information about the schema
        result = component.get_schema_info()

        assert isinstance(result, Data)
        schema_data = result.data

        # Check the structure of returned schema info
        assert "total_columns" in schema_data
        assert "columns_with_load_from_db" in schema_data
        assert "columns_with_static_defaults" in schema_data

    def test_load_table_data_error_handling(self):
        """Test error handling in load_table_data."""
        component = TableSchemaDemoComponent()

        # Create a mock scenario that would cause an error
        # We'll use an object that can't be converted properly
        class UnconvertibleObject:
            pass

        # This should still work due to the error handling that converts to string
        component.table_data = [UnconvertibleObject()]

        result = component.load_table_data()

        # Should convert the unconvertible object to a string representation
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Data)

    def test_component_outputs(self):
        """Test that the component has the expected outputs."""
        component = TableSchemaDemoComponent()

        assert len(component.outputs) == 2

        output_names = [output.name for output in component.outputs]
        assert "data_list" in output_names
        assert "schema_info" in output_names

        # Check output methods exist
        assert hasattr(component, "load_table_data")
        assert hasattr(component, "get_schema_info")


class TestTableSchemaDemoIntegration:
    """Integration tests for TableSchemaDemoComponent with load_from_db functionality."""

    def test_column_schema_with_load_from_db_true(self):
        """Test columns configured with load_from_db=True."""
        column = Column(name="api_key", display_name="API Key", default="default-key", load_from_db=True, type="text")

        assert column.load_from_db is True
        assert column.default == "default-key"
        assert column.name == "api_key"

    def test_column_schema_with_load_from_db_false(self):
        """Test columns configured with load_from_db=False."""
        column = Column(name="timeout", display_name="Timeout", default=30, load_from_db=False, type="integer")

        assert column.load_from_db is False
        assert column.default == "30"
        assert column.name == "timeout"

    def test_table_component_schema_serialization(self):
        """Test that table schema with load_from_db can be serialized."""
        component = TableSchemaDemoComponent()
        table_input = component.inputs[0]

        # The schema should be serializable (important for frontend/backend communication)
        assert table_input.table_schema is not None

        # Each column should be serializable
        for column in table_input.table_schema:
            column_dict = column.model_dump()
            assert "load_from_db" in column_dict
            assert isinstance(column_dict["load_from_db"], bool)

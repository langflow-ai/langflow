from lfx.custom.custom_component.component import Component
from lfx.io import Output, TableInput
from lfx.schema.data import Data
from lfx.schema.table import Column


class TableSchemaDemoComponent(Component):
    display_name = "Table Schema Demo"
    description = "Demonstrates table column schema with load_from_db functionality for global variables"
    icon = "table"
    name = "TableSchemaDemo"

    inputs = [
        TableInput(
            name="table_data",
            display_name="Table Data",
            info="Table with schema defining which columns can load from global variables",
            table_schema=[
                Column(
                    name="username",
                    display_name="Username",
                    type="text",
                    default="admin",
                    load_from_db=True,  # This column can load from global variables
                    description="Username that can be loaded from global variables",
                ),
                Column(
                    name="email",
                    display_name="Email Address",
                    type="text",
                    default="user@example.com",
                    load_from_db=True,  # This column can load from global variables
                    description="Email address that can be loaded from global variables",
                ),
                Column(
                    name="role",
                    display_name="User Role",
                    type="text",
                    default="user",
                    load_from_db=False,  # This column uses static default
                    description="User role with static default value",
                ),
                Column(
                    name="active",
                    display_name="Active Status",
                    type="boolean",
                    default=True,
                    load_from_db=False,  # This column uses static default
                    description="Whether the user is active",
                ),
            ],
            value=[
                {"username": "admin", "email": "admin@example.com", "role": "admin", "active": True},
                {"username": "user1", "email": "user1@example.com", "role": "user", "active": True},
            ],
        ),
    ]

    outputs = [
        Output(name="data_list", display_name="Data List", method="load_table_data"),
        Output(name="schema_info", display_name="Schema Info", method="get_schema_info"),
    ]

    def load_table_data(self) -> list[Data]:
        """Convert table input data to a list of Data objects."""
        if not self.table_data:
            self.status = "No table data provided."
            return []

        try:
            # Convert each row in the table to a Data object
            result = []
            for i, row in enumerate(self.table_data):
                if isinstance(row, dict):
                    # Create Data object with the row data
                    data_obj = Data(data=row)
                    result.append(data_obj)
                elif isinstance(row, Data):
                    # Already a Data object, just add it
                    result.append(row)
                else:
                    # Try to convert to Data object
                    data_obj = Data(data={"row": str(row), "index": i})
                    result.append(data_obj)

        except Exception as e:
            error_message = f"Error processing table data: {e}"
            self.status = error_message
            raise ValueError(error_message) from e
        else:
            self.status = f"Successfully loaded {len(result)} rows from table data"
            return result

    def get_schema_info(self) -> Data:
        """Return information about the table schema and which columns load from DB."""
        try:
            # Get the table schema from the input
            table_input = getattr(self.inputs[0], "table_schema", None)

            schema_info = {
                "total_columns": len(table_input) if table_input else 0,
                "columns_with_load_from_db": [],
                "columns_with_static_defaults": [],
            }

            if table_input:
                for col in table_input:
                    col_info = {
                        "name": col.name,
                        "display_name": col.display_name,
                        "type": col.type,
                        "default": col.default,
                    }

                    if col.load_from_db:
                        schema_info["columns_with_load_from_db"].append(col_info)
                    else:
                        schema_info["columns_with_static_defaults"].append(col_info)
            else:
                self.status = "No table schema available"
                return Data(data={"error": "No table schema available"})

            return Data(data=schema_info)

        except ValueError as e:
            error_message = f"Error getting schema info: {e}"
            self.status = error_message
            return Data(data={"error": error_message})

import os
from contextlib import contextmanager

from databricks import sql
from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output, SecretStrInput, StrInput
from langflow.schema.data import Data


class DataBricksQueryComponent(Component):
    display_name = "DataBricks Query"
    description = "Execute SQL queries on DataBricks using server hostname, HTTP path, and access token."
    documentation: str = "https://docs.databricks.com/dev-tools/python-sql-connector.html"
    icon = "DataBricks"
    name = "DataBricksQuery"

    inputs = [
        StrInput(
            name="server_hostname",
            display_name="Server Hostname",
            info="DataBricks server hostname (e.g., your-workspace.cloud.databricks.com)",
            required=True,
        ),
        StrInput(
            name="http_path",
            display_name="HTTP Path",
            info="DataBricks HTTP path for SQL endpoint",
            required=True,
        ),
        SecretStrInput(
            name="access_token",
            display_name="Access Token",
            info="DataBricks personal access token",
            value=os.getenv("DATABRICKS_TOKEN", ""),
            required=True,
        ),
        MessageTextInput(
            name="sql_query",
            display_name="SQL Query",
            info="SQL query to execute on DataBricks",
            value="SELECT * FROM samples.nyctaxi.trips LIMIT 10",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Query Results", name="results", method="execute_query"),
        Output(display_name="Row Count", name="row_count", method="get_row_count"),
    ]

    @contextmanager
    def _get_cursor(self):
        """Context manager for Databricks connection and cursor.
        
        Yields a cursor that can be used for executing queries.
        Automatically handles connection lifecycle.
        """
        with sql.connect(
            server_hostname=self.server_hostname,
            http_path=self.http_path,
            access_token=self.access_token
        ) as connection:
            with connection.cursor() as cursor:
                yield cursor

    def execute_query(self) -> Data:
        """Execute the SQL query and return results."""
        try:
            with self._get_cursor() as cursor:
                cursor.execute(self.sql_query)
                result = cursor.fetchall()

                # Convert to list of dictionaries for better handling
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                data = [dict(zip(columns, row, strict=False)) for row in result]

                self.status = f"Query executed successfully. Retrieved {len(data)} rows."
                return Data(value=data)

        except Exception as e:
            error_msg = f"Error executing query: {e!s}"
            self.status = error_msg
            return Data(value={"error": error_msg})

    def get_row_count(self) -> Data:
        """Get the number of rows returned by the query using COUNT(*)"""
        try:
            with self._get_cursor() as cursor:
                # Wrap query to count rows without fetching all data
                count_query = f"SELECT COUNT(*) FROM ({self.sql_query}) AS subquery"
                cursor.execute(count_query)
                result = cursor.fetchone()
                row_count = result[0] if result else 0

                self.status = f"Query returned {row_count} rows."
                return Data(value=row_count)

        except Exception as e:
            error_msg = f"Error getting row count: {e!s}"
            self.status = error_msg
            return Data(value={"error": error_msg})

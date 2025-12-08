import os

from databricks import sql
from dotenv import load_dotenv
from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output, SecretStrInput, StrInput
from langflow.schema.data import Data

# Load environment variables
load_dotenv()


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

    def execute_query(self) -> Data:
        """Execute the SQL query and return results."""
        try:
            with sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                access_token=self.access_token
            ) as connection:
                with connection.cursor() as cursor:
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
        """Get the number of rows returned by the query."""
        try:
            with sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                access_token=self.access_token
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(self.sql_query)
                    result = cursor.fetchall()
                    row_count = len(result)

                    self.status = f"Query returned {row_count} rows."
                    return Data(value=row_count)

        except Exception as e:
            error_msg = f"Error getting row count: {e!s}"
            self.status = error_msg
            return Data(value={"error": error_msg})

##pre-requisite pip install snowflake-connector-python
import json
from json.decoder import JSONDecodeError

import snowflake.connector

from langflow.custom import Component
from langflow.field_typing import Message
from langflow.io import MessageTextInput, Output


class SnowflakeSQLExecutorComponent(Component):
    display_name = "Snowflake SQL Executor"
    description = "Execute SQL queries on Snowflake."
    name = "SnowflakeExecutor"
    beta: bool = True

    inputs = [
        MessageTextInput(
            name="account",
            display_name="Snowflake Account",
            info="Snowflake account identifier, e.g., xy12345.us-east-1",
            required=True,
        ),
        MessageTextInput(
            name="user",
            display_name="Username",
            info="Snowflake username for authentication.",
            required=True,
        ),
        MessageTextInput(
            name="password",
            display_name="Password",
            info="Snowflake password for authentication.",
            required=True,
        ),
        MessageTextInput(
            name="warehouse",
            display_name="Warehouse",
            info="Name of the Snowflake warehouse (compute resource).",
            required=True,
        ),
        MessageTextInput(
            name="database",
            display_name="Database",
            info="Snowflake database name.",
            required=True,
        ),
        MessageTextInput(
            name="schema",
            display_name="Schema",
            info="Snowflake schema name.",
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="SQL Query",
            info="The SQL query to execute on Snowflake.",
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Query Result",
            name="rows",
            method="execute_sql",
        )
    ]

    def execute_sql(self) -> Message:
        """Connect to Snowflake using provided credentials,
        execute the SQL query, and return the results as JSON.
        """
        try:
            # Ensure we have a non-empty query string
            sql_query = self.query.strip() if self.query else ""
            if not sql_query:
                raise ValueError("No valid SQL query provided.")

            # Create a Snowflake connection
            conn = snowflake.connector.connect(
                user=self.user,
                password=self.password,
                account=self.account,
                warehouse=self.warehouse,
                database=self.database,
                schema=self.schema,
            )
        except JSONDecodeError as e:
            msg = "Invalid JSON input encountered (not typically expected here)."
            raise ValueError(msg) from e
        except Exception as e:
            msg = f"Error establishing Snowflake connection: {e}"
            raise ValueError(msg) from e

        try:
            # Execute the query
            cursor = conn.cursor()
            cursor.execute(sql_query)

            # Fetch rows
            rows = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]

            # Convert rows to list of dicts
            output_dict = [dict(zip(column_names, row, strict=False)) for row in rows]
            output_json = json.dumps(output_dict, indent=4, default=str)

            # Close the cursor/connection
            cursor.close()
            conn.close()

        except Exception as e:
            msg = f"Error executing Snowflake SQL query: {e}"
            raise ValueError(msg) from e

        # Store the result in the component's status (optional, for logging)
        self.status = output_json
        # Return a LangFlow Message object containing the query results
        return Message(text=json.dumps(output_dict, indent=2))

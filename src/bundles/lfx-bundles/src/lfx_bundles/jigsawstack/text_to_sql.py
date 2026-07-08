from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, QueryInput, SecretStrInput, StrInput
from lfx.schema.data import Data


class JigsawStackTextToSQLComponent(Component):
    display_name = "Text to SQL"
    description = "Convert natural language to SQL queries using JigsawStack AI"
    documentation = "https://jigsawstack.com/docs/api-reference/ai/text-to-sql"
    icon = "JigsawStack"
    name = "JigsawStackTextToSQL"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="JigsawStack API Key",
            info="Your JigsawStack API key for authentication",
            required=True,
        ),
        QueryInput(
            name="prompt",
            display_name="Prompt",
            info="Natural language description of the SQL query you want to generate",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="sql_schema",
            display_name="SQL Schema",
            info=(
                "The database schema information. Can be a CREATE TABLE statement or schema description. "
                "Specifying this parameter improves SQL generation accuracy by applying "
                "database-specific syntax and optimizations."
            ),
            required=False,
            tool_mode=True,
        ),
        StrInput(
            name="file_store_key",
            display_name="File Store Key",
            info=(
                "The key used to store the database schema on Jigsawstack file Storage. "
                "Not required if sql_schema is specified."
            ),
            required=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="SQL Query", name="sql_query", method="generate_sql"),
    ]

    def generate_sql(self) -> Data:
        try:
            from jigsawstack import JigsawStack, JigsawStackError
        except ImportError as e:
            jigsawstack_import_error = (
                "JigsawStack package not found. Please install it using: pip install jigsawstack>=0.2.7"
            )
            raise ImportError(jigsawstack_import_error) from e

        try:
            schema_error = "Either 'sql_schema' or 'file_store_key' must be provided"
            if not self.sql_schema and not self.file_store_key:
                raise ValueError(schema_error)

            # build request object
            params = {"prompt": self.prompt}

            if self.sql_schema:
                params["sql_schema"] = self.sql_schema
            if self.file_store_key:
                params["file_store_key"] = self.file_store_key

            client = JigsawStack(api_key=self.api_key)
            response = client.text_to_sql(params)

            api_error_msg = "JigsawStack API returned unsuccessful response"
            if not response.get("success", False):
                raise ValueError(api_error_msg)

            return Data(data=response)

        except ValueError:
            raise
        except JigsawStackError as e:
            error_data = {"error": str(e), "success": False}
            self.status = f"Error: {e!s}"
            return Data(data=error_data)

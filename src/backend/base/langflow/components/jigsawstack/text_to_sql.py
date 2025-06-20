from langflow.custom.custom_component.component import Component
from langflow.io import Output, SecretStrInput, StrInput, QueryInput, MessageTextInput
from langflow.schema.data import Data


class JigsawStackTextToSQLComponent(Component):
    display_name = "Text To SQL"
    description = "Convert natural language to SQL queries for various database types."
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
            info="The natural language prompt that will be translated to an SQL query. Minimum length: 10 characters",
            required=True,
        ),
        MessageTextInput(
            name="sql_schema",
            display_name="SQL Schema",
            info="The database schema where the query will be run. Not required if file_store_key is specified.",
            required=False,
        ),
        StrInput(
            name="database",
            display_name="Database",
            info="The database type to generate SQL for. Supported values are postgresql, mysql, or sqlite. Specifying this parameter improves SQL generation accuracy by applying database-specific syntax and optimizations.",
            required=False,
        ),
        StrInput(
            name="file_store_key",
            display_name="File Store Key",
            info="The key used to store the database schema on Jigsawstack file Storage. Not required if sql_schema is specified.",
            required=False,
        )
    ]

    outputs = [
        Output(display_name="TextToSQL Results", name="text_to_sql_results", method="text_to_sql"),
    ]

    def text_to_sql(self) -> Data:
        try:
            from jigsawstack import JigsawStack
        except ImportError as e:
            raise ImportError(
                "JigsawStack package not found"
            ) from e

        try:
            client = JigsawStack(api_key=self.api_key)
            
            #build request object
            params = {}
            if self.prompt:
                params["prompt"] = self.prompt
            if self.sql_schema:
                params["sql_schema"] = self.sql_schema
            if self.database:
                params["database"] = self.database
            if self.file_store_key:
                params["file_store_key"] = self.file_store_key
    
            response = client.text_to_sql(params)
            
            if not response.get("success", False):
                raise ValueError("JigsawStack API returned unsuccessful response")
            
            return Data(data=response)
            
        except Exception as e:
            error_data = {
                "error": str(e),
                "success": False
            }
            self.status = f"Error: {str(e)}"
            return Data(data=error_data)


   
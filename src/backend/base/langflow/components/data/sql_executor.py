from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_community.utilities import SQLDatabase

from langflow.custom import CustomComponent
from langflow.field_typing import Text


class SQLExecutorComponent(CustomComponent):
    display_name = "SQL Query"
    description = "Execute SQL query."
    name = "SQLExecutor"
    beta: bool = True

    def build_config(self):
        return {
            "database_url": {
                "display_name": "Database URL",
                "info": "The URL of the database.",
            },
            "include_columns": {
                "display_name": "Include Columns",
                "info": "Include columns in the result.",
            },
            "passthrough": {
                "display_name": "Passthrough",
                "info": "If an error occurs, return the query instead of raising an exception.",
            },
            "add_error": {
                "display_name": "Add Error",
                "info": "Add the error to the result.",
            },
        }

    def clean_up_uri(self, uri: str) -> str:
        if uri.startswith("postgresql://"):
            uri = uri.replace("postgresql://", "postgres://")
        return uri.strip()

    def build(
        self,
        query: str,
        database_url: str,
        *,
        include_columns: bool = False,
        passthrough: bool = False,
        add_error: bool = False,
        **kwargs,
    ) -> Text:
        _ = kwargs
        error = None
        try:
            database = SQLDatabase.from_uri(database_url)
        except Exception as e:
            msg = f"An error occurred while connecting to the database: {e}"
            raise ValueError(msg) from e
        try:
            tool = QuerySQLDataBaseTool(db=database)
            result = tool.run(query, include_columns=include_columns)
            self.status = result
        except Exception as e:
            result = str(e)
            self.status = result
            if not passthrough:
                raise
            error = repr(e)

        if add_error and error is not None:
            result = f"{result}\n\nError: {error}\n\nQuery: {query}"
        elif error is not None:
            # Then we won't add the error to the result
            # but since we are in passthrough mode, we will return the query
            result = query

        return result

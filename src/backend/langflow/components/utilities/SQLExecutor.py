from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_experimental.sql.base import SQLDatabase

from langflow import CustomComponent
from langflow.field_typing import Text


class SQLExecutorComponent(CustomComponent):
    display_name = "SQL Executor"
    description = "Execute SQL query."

    def build_config(self):
        return {
            "database": {"display_name": "Database"},
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

    def build(
        self,
        query: str,
        database: SQLDatabase,
        include_columns: bool = False,
        passthrough: bool = False,
        add_error: bool = False,
    ) -> Text:
        error = None
        try:
            tool = QuerySQLDataBaseTool(db=database)
            result = tool.run(query, include_columns=include_columns)
            self.status = result
        except Exception as e:
            result = str(e)
            self.status = result
            if not passthrough:
                raise e
            error = repr(e)

        if add_error and error is not None:
            result = f"{result}\n\nError: {error}\n\nQuery: {query}"
        elif error is not None:
            # Then we won't add the error to the result
            # but since we are in passthrough mode, we will return the query
            result = query

        return result

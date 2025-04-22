import logging

from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_community.utilities import SQLDatabase

from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message
from langflow.services.cache.utils import CacheMiss



class SQLComponent(ComponentWithCache):
    """A sql component."""

    display_name = "SQL Query"
    description = "Execute SQL Query"
    icon = "layout-template"
    name = "SQLComponent"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.db = None
        self.maybe_create_db()

    def maybe_create_db(self):
        if self.database_url != "":
            cached_db = self._shared_component_cache.get(self.database_url)
            if not isinstance(cached_db, CacheMiss):
                self.db = cached_db
                return
            logger.info("Connecting to database")
            try:
                self.db = SQLDatabase.from_uri(self.database_url)
            except Exception as e:
                msg = f"An error occurred while connecting to the database: {e}"
                raise ValueError(msg) from e
            self._shared_component_cache.set(self.database_url, self.db)

    inputs = [
        MessageTextInput(
            name="database_url",
            display_name="Database URL",
            placeholder="Enter a URL...",
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            placeholder="query...",
            tool_mode=True,
        ),
        MessageTextInput(
            name="include_columns",
            display_name="Include Columns",
            placeholder="False",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Message", name="text", method="build_component"),
    ]

    def build_component(
        self,
    ) -> Message:
        error = None
        self.maybe_create_db()
        try:
            tool = QuerySQLDataBaseTool(db=self.db)
            result = tool.run(self.query, include_columns=self.include_columns)
            self.status = result
        except Exception as e:
            msg = f"An error occurred while running the SQL Query: {e}"
            logger.exception(msg)
            result = str(e)
            self.status = result
            error = repr(e)

        if error is not None:
            result = f"{result}\n\nError: {error}\n\nQuery: {self.query}"
        elif error is not None:
            # Then we won't add the error to the result
            result = self.query

        return Message(text=result)

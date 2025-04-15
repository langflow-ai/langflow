import logging

from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_community.utilities import SQLDatabase

from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message

logger = logging.getLogger(__name__)


class SQLComponent(Component):
    """A sql component."""

    display_name = "SQL"
    description = "Load and parse child links from a root URL recursively"
    icon = "layout-template"
    name = "SQLComponent"

    inputs = [
        MessageTextInput(
            name="database_url",
            display_name="database url",
            placeholder="Enter a URL...",
            list_add_label="Add URL",
        ),
        MessageTextInput(
            name="query",
            display_name="query",
            placeholder="query...",
            list_add_label="query",
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
        try:
            database = SQLDatabase.from_uri(self.database_url)
        except Exception as e:
            msg = f"An error occurred while connecting to the database: {e}"
            raise ValueError(msg) from e
        try:
            tool = QuerySQLDataBaseTool(db=database)
            result = tool.run(self.query, include_columns=True)
            self.status = result
        except Exception as e:  # noqa: BLE001
            result = str(e)
            self.status = result
            error = repr(e)

        if error is not None:
            result = f"{result}\n\nError: {error}\n\nQuery: {self.query}"
        elif error is not None:
            # Then we won't add the error to the result
            result = self.query

        return Message(text=result)

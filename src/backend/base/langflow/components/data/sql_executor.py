from typing import TYPE_CHECKING, Any

from langchain_community.utilities import SQLDatabase
from sqlalchemy.exc import SQLAlchemyError

from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.io import BoolInput, MessageTextInput, Output
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.services.cache.utils import CacheMiss

if TYPE_CHECKING:
    from sqlalchemy.engine import Result


class SQLComponent(ComponentWithCache):
    """A sql component."""

    display_name = "SQL Query"
    description = "Execute SQL Query"
    icon = "database"
    name = "SQLComponent"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.db: SQLDatabase = None

    def maybe_create_db(self):
        if self.database_url != "":
            cached_db = self._shared_component_cache.get(self.database_url)
            if not isinstance(cached_db, CacheMiss):
                self.db = cached_db
                return
            self.log("Connecting to database")
            try:
                self.db = SQLDatabase.from_uri(self.database_url)
            except Exception as e:
                msg = f"An error occurred while connecting to the database: {e}"
                raise ValueError(msg) from e
            self._shared_component_cache.set(self.database_url, self.db)

    inputs = [
        MessageTextInput(name="database_url", display_name="Database URL", required=True),
        MessageTextInput(name="query", display_name="SQL Query", tool_mode=True, required=True),
        BoolInput(name="include_columns", display_name="Include Columns", value=True, tool_mode=True),
        BoolInput(
            name="add_error",
            display_name="Add Error",
            value=False,
            tool_mode=True,
            info="If True, the error will be added to the result",
        ),
    ]

    outputs = [
        Output(display_name="Message", name="text", method="build_component"),
        Output(display_name="Data", name="data", method="build_data"),
        Output(display_name="DataFrame", name="dataframe", method="build_dataframe"),
    ]

    def build_component(
        self,
    ) -> Message:
        error = None
        self.maybe_create_db()
        try:
            result = self.db.run(self.query, include_columns=self.include_columns)
            self.status = result
        except SQLAlchemyError as e:
            msg = f"An error occurred while running the SQL Query: {e}"
            self.log(msg)
            result = str(e)
            self.status = result
            error = repr(e)

        if self.add_error and error is not None:
            result = f"{result}\n\nError: {error}\n\nQuery: {self.query}"
        elif error is not None:
            # Then we won't add the error to the result
            result = self.query

        return Message(text=result)

    def __execute_query(self) -> list[dict[str, Any]]:
        self.maybe_create_db()
        try:
            cursor: Result[Any] = self.db.run(self.query, fetch="cursor")
            return [x._asdict() for x in cursor.fetchall()]
        except SQLAlchemyError as e:
            msg = f"An error occurred while running the SQL Query: {e}"
            self.log(msg)
            raise ValueError(msg) from e

    def build_dataframe(self) -> DataFrame:
        result = self.__execute_query()
        df_result = DataFrame(result)
        self.status = df_result
        return df_result

    def build_data(self) -> Data:
        result = self.__execute_query()
        data_result = Data(data={"result": result})
        self.status = data_result
        return data_result

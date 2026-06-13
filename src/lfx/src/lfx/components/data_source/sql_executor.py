import re
from typing import TYPE_CHECKING, Any

from langchain_community.utilities import SQLDatabase
from sqlalchemy.exc import SQLAlchemyError

from lfx.custom.custom_component.component_with_cache import ComponentWithCache
from lfx.io import BoolInput, MessageTextInput, MultilineInput, Output
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.services.cache.utils import CacheMiss

if TYPE_CHECKING:
    from sqlalchemy.engine import Result


class SQLComponent(ComponentWithCache):
    """A sql component."""

    display_name = "SQL Database"
    description = "Executes SQL queries on SQLAlchemy-compatible databases."
    documentation: str = "https://docs.langflow.org/sql-database"
    icon = "database"
    name = "SQLComponent"
    metadata = {"keywords": ["sql", "database", "query", "db", "fetch"]}

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.db: SQLDatabase = None
        self._named_parameters: list[str] = []

    def maybe_create_db(self):
        if self.database_url != "":
            if self._shared_component_cache:
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
            if self._shared_component_cache:
                self._shared_component_cache.set(self.database_url, self.db)

    inputs = [
        MessageTextInput(name="database_url", display_name="Database URL", required=True),
        MultilineInput(
            name="query",
            display_name="SQL Query",
            tool_mode=True,
            required=True,
            real_time_refresh=True,
            info="SQL Query to execute. Use :param_name for parameters.",
        ),
        MultilineInput(
            name="query_fallback",
            display_name="SQL Query Fallback",
            tool_mode=False,
            required=False,
            advanced=True,
            real_time_refresh=True,
            info="SQL Query to execute if the first query fails. Use :param_name for parameters.",
        ),
        BoolInput(name="include_columns", display_name="Include Columns", value=True, tool_mode=True, advanced=True),
        BoolInput(
            name="add_error",
            display_name="Add Error",
            value=False,
            tool_mode=True,
            info="If True, the error will be added to the result",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result Table", name="run_sql_query", method="run_sql_query"),
    ]

    def _extract_parameters_from_query(self, query: str, query_fallback: str = "") -> set[str]:
        """Extract parameter names from SQL query using various parameter formats.

        Args:
            query: SQL query string
            query_fallback: SQL query string to use if the first query fails

        Returns:
            Set of unique parameter names found in the query
        """
        if not isinstance(query, str):
            return set()

        queries_combined = query + "\n" + query_fallback

        # SQL identifier pattern (starts with letter/underscore, followed by alphanumeric/underscore)
        identifier_pattern = r"[a-zA-Z_][a-zA-Z0-9_]*"

        # Define all parameter patterns to extract
        parameter_patterns = [
            rf":({identifier_pattern})",  # :parameter format: :user_id
        ]

        # Extract fields using all patterns
        extracted_fields = []
        for pattern in parameter_patterns:
            matches = re.findall(pattern, queries_combined)
            extracted_fields.extend(matches)

        # Return unique field names
        return set(extracted_fields)

    async def update_build_config(
        self,
        build_config: dict,
        field_value: str | dict,
        field_name: str | None = None,
    ) -> dict:
        if field_name in {"query", "query_fallback"}:
            # Extract field names from various parameter formats:
            # - SQLAlchemy named parameters: %(param_name)s
            if isinstance(field_value, str):
                # Define default keys that should always be preserved
                default_keys = {
                    "code",
                    "_type",
                    "database_url",
                    "query",
                    "query_fallback",
                    "include_columns",
                    "add_error",
                }

                # Get query and query_fallback from build_config
                # If the query or query_fallback is a dict, get the value, otherwise get the string

                def get_query_value(build_config: dict, key: str) -> str:
                    if isinstance(build_config.get(key), dict):
                        return build_config.get(key, {}).get("value", "")
                    return build_config.get(key, "")

                query = get_query_value(build_config, "query")
                query_fallback = get_query_value(build_config, "query_fallback")

                # Extract parameters from query
                unique_fields = self._extract_parameters_from_query(query, query_fallback)
                # Find all current dynamic fields in build_config (not in default_keys)
                current_dynamic_fields = {
                    key for key in build_config if key not in default_keys and isinstance(build_config[key], dict)
                }

                # Remove fields from build_config that are dynamic but not in unique_fields
                fields_to_remove = current_dynamic_fields - unique_fields
                for field_to_remove in fields_to_remove:
                    build_config.pop(field_to_remove, None)

                # Create Input fields for each extracted field name
                new_fields = {}
                for field_name_extracted in unique_fields:
                    # Add to build_config if not already present
                    if field_name_extracted not in build_config:
                        field = MessageTextInput(
                            display_name=field_name_extracted.replace("_", " ").title(),
                            name=field_name_extracted,
                            info=f"Value for {field_name_extracted} parameter in SQL query",
                            value="",
                        )
                        new_fields[field.name] = field.to_dict()

                # Add new_fields to build_config
                build_config.update(new_fields)

                # Update self._named_parameters with the new extracted fields
                self._named_parameters = list(unique_fields)

            return build_config

        return build_config

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

    def __execute_query(self, query: str) -> list[dict[str, Any]]:
        self.maybe_create_db()
        try:
            # Extract parameters from query at execution time
            # This ensures we always have the latest parameters even if update_build_config wasn't called
            extracted_params = self._extract_parameters_from_query(query)

            parameters = {}
            if extracted_params:
                # Get parameter values from component inputs
                for key in extracted_params:
                    value = getattr(self, key, None)
                    if value is not None:
                        if isinstance(value, str):
                            parameters[key] = value
                        else:
                            parameters[key] = value.text  # Get the text value from the Message object

                # Filter out None values (parameters that weren't set)
                parameters = {k: v for k, v in parameters.items() if v is not None}
            cursor: Result[Any] = self.db.run(query, fetch="cursor", parameters=parameters)
            if isinstance(cursor, list):
                return cursor
            return [x._asdict() for x in cursor.fetchall()]
        except SQLAlchemyError as e:
            msg = f"An error occurred while running the SQL Query: {e}"
            self.log(msg)
            raise ValueError(msg) from e

    def run_sql_query(self) -> DataFrame:
        result = None
        try:
            result = self.__execute_query(self.query)
        except Exception as e:
            if self.query_fallback and self.query_fallback != "":
                try:
                    result = self.__execute_query(self.query_fallback)
                except Exception as e:
                    msg = f"An error occurred while running the SQL Query Fallback: {e}"
                    self.log(msg)
                    raise ValueError(msg) from e
            else:
                msg = f"An error occurred while running the SQL Query: {e}"
                self.log(msg)
                raise ValueError(msg) from e

        df_result = DataFrame(result)
        self.status = df_result
        return df_result

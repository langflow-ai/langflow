import json
import subprocess
import tempfile
from typing import Any, cast

import jq
import pandas as pd
from loguru import logger

from langflow.custom import Component
from langflow.io import DataInput, IntInput, MultilineInput, Output
from langflow.schema import Data
from langflow.schema.dataframe import DataFrame


class FilterDataComponent(Component):
    """A component for filtering data using various methods."""

    display_name = "Filter Data"
    description = "Filter data using various methods like index, JQ query, and column selection."
    icon = "filter"
    name = "FilterData"
    max_query_length = 1000  # Maximum length for JQ queries

    inputs = [
        DataInput(
            name="input_value",
            display_name="Input",
            info="The input data to filter. Can be a single Data object or a list of Data objects.",
            input_types=["Data"],
        ),
        MultilineInput(
            name="select_columns",
            display_name="Select Columns",
            info="List of columns to select from the data.",
            list=True,
            required=False,
        ),
        MultilineInput(
            name="jq_query",
            display_name="JQ Query",
            info="JQ query to filter the data.",
            required=False,
        ),
        IntInput(
            name="index",
            display_name="Index",
            info="Index to select from the data.",
            required=False,
        ),
    ]

    outputs = [
        Output(
            name="filtered_data",
            display_name="Filtered Data",
            description="The filtered data.",
            output_types=["Data", "list[Data]"],
            method="process_data",
        ),
        Output(
            name="dataframe",
            display_name="DataFrame",
            description="The filtered data as a DataFrame.",
            output_types=["DataFrame"],
            method="process_dataframe",
        ),
    ]

    def _parse_data(self, data: Data) -> str:
        """Parse data object to string."""
        if not isinstance(data, Data):
            error_msg = "Input must be a Data object"
            raise TypeError(error_msg)

        try:
            return json.dumps(data.data)
        except (TypeError, ValueError) as e:
            logger.error("Error parsing data: %s", e)
            return ""

    def _apply_jq_query(self, data_str: str, jq_query: str) -> Any:
        """Apply JQ query to data string."""
        try:
            # Create a temporary file to store the data
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as temp_file:
                temp_file.write(data_str)
                temp_file.flush()

                # Run JQ command with -c to get compact output
                # Input is validated by _is_safe_jq_query to prevent command injection
                command = ["jq", "-c", jq_query, temp_file.name]
                # nosec B603 - Input is validated by _is_safe_jq_query
                result = subprocess.check_output(
                    command,
                    text=True,
                    stderr=subprocess.PIPE,
                )
                # Security: This subprocess call is safe because the input is validated by _is_safe_jq_query

                # Parse output
                output_str = result.strip()
                if not output_str:
                    return None

                # If there are multiple lines, parse each line separately
                if "\n" in output_str:
                    results = []
                    for line in output_str.split("\n"):
                        try:
                            results.append(json.loads(line))
                        except json.JSONDecodeError:
                            results.append(line)
                    return results

                # Try to parse single line as JSON
                try:
                    return json.loads(output_str)
                except json.JSONDecodeError:
                    return output_str

        except subprocess.CalledProcessError as e:
            error_msg = f"Error running JQ query: {e!s}"
            logger.error("Error running JQ command: %s", e)
            raise ValueError(error_msg) from e
        except Exception as e:  # pylint: disable=broad-except
            error_msg = f"Error applying JQ query: {e!s}"
            logger.error("Error applying JQ query: %s", e)
            raise ValueError(error_msg) from e

    def _apply_column_filter(self, data: Any, columns: list[str]) -> Any:
        """Filter data by specified columns."""
        if not isinstance(data, dict):
            return data

        return {k: v for k, v in data.items() if k in columns}

    def process_dataframe(self) -> DataFrame:
        """Process data and return as DataFrame."""
        result = self.process_data()
        data_list = [result.data] if isinstance(result, Data) else [item.data for item in result]
        dataframe = pd.DataFrame(data_list)
        return cast(DataFrame, dataframe)

    def _convert_to_dataframe(self) -> pd.DataFrame:
        """Convert input data to DataFrame."""
        if not self.input_value:
            return pd.DataFrame()

        if isinstance(self.input_value, Data):
            return pd.DataFrame([self.input_value.data])

        data_list = [item.data for item in self.input_value]
        return pd.DataFrame(data_list)

    def _filter_by_index(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Filter DataFrame by index."""
        if self.index is not None:
            return dataframe.iloc[[self.index]]
        return dataframe

    def _filter_by_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Filter DataFrame by selected columns."""
        if self.select_columns:
            return dataframe[list(self.select_columns)]
        return dataframe

    def _is_safe_jq_query(self, query: str) -> bool:
        """Validate JQ query for security."""
        # Basic validation - only allow alphanumeric characters, dots, brackets,
        # spaces, and common JQ operators
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.[]() +-*/<>=|,")
        return all(c in safe_chars for c in query) and len(query) < self.max_query_length

    def process_data(self) -> Data | list[Data]:
        """Process data and return as Data object or list of Data objects."""
        try:
            if not self.input_value:
                return None

            # Convert input to DataFrame
            dataframe = self._convert_to_dataframe()

            # Apply filtering based on index
            if self.index is not None:
                dataframe = self._filter_by_index(dataframe)

            # Apply filtering based on selected columns
            if self.select_columns:
                dataframe = self._filter_by_columns(dataframe)

            # Apply JQ query filtering if provided
            if self.jq_query:
                # Validate JQ query for security
                if not self._is_safe_jq_query(self.jq_query):
                    error_msg = f"Invalid or unsafe JQ query: {self.jq_query}"
                    raise ValueError(error_msg)

                try:
                    # Convert DataFrame to JSON string
                    json_str = json.dumps(dataframe.to_dict(orient="records"))

                    # Apply JQ query using jq library
                    result = jq.compile(self.jq_query).input(json.loads(json_str)).first()

                    if result is None:
                        return None

                    # Handle primitive values from JQ query
                    if isinstance(result, int | float | str | bool):
                        return Data(data=result)

                    # Handle array results from JQ query with array operators
                    if isinstance(result, list):
                        return [Data(data=item) for item in result]

                    # Handle object results from JQ query
                    return Data(data=result)

                except ValueError as e:
                    error_msg = f"Error executing JQ query: {e!s}"
                    raise ValueError(error_msg) from e

            # Return filtered DataFrame as list of Data objects
            records = dataframe.to_dict(orient="records")
            return [Data(data=record) for record in records]

        except Exception as e:
            error_msg = f"Error in FilterDataComponent: {e!s}"
            raise ValueError(error_msg) from e

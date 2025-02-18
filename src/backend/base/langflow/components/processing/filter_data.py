import json
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
            output_types=["Data"],
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
            # Parse input data string to JSON
            data = json.loads(data_str)

            # Apply JQ query using jq library
            result = jq.compile(jq_query).input(data).first()

            if result is None:
                return None

            # Handle primitive values from JQ query
            if isinstance(result, int | float | str | bool):
                return result

            # Handle array results from JQ query
            if isinstance(result, list):
                return result

        except json.JSONDecodeError as e:
            error_msg = f"Error parsing JSON data: {e!s}"
            logger.error("Error parsing JSON data: %s", e)
            raise ValueError(error_msg) from e
        except ValueError as e:
            error_msg = f"Error executing JQ query: {e!s}"
            logger.error("Error executing JQ query: %s", e)
            raise ValueError(error_msg) from e
        except Exception as e:  # pylint: disable=broad-except
            error_msg = f"Error applying JQ query: {e!s}"
            logger.error("Error applying JQ query: %s", e)
            raise ValueError(error_msg) from e
        return result

    def _apply_column_filter(self, data: Any, columns: list[str]) -> Any:
        """Filter data by specified columns."""
        if not isinstance(data, dict):
            return data

        return {k: data[k] for k in columns if k in data}

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
        if len(query) >= self.max_query_length:
            return False
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.[]() +-*/<>=|,"
        return all(c in safe_chars for c in query)

    def process_data(self) -> Data:
        """Process data and return as Data object or list of Data objects."""
        try:
            if not self.input_value:
                return Data(data={})

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

                # Convert DataFrame to JSON string
                json_str = json.dumps(dataframe.to_dict(orient="records"))

                # Apply JQ query and get result
                result = self._apply_jq_query(json_str, self.jq_query)

                if result is None:
                    return Data(data={})

                # Handle primitive values from JQ query
                if isinstance(result, int | float | str | bool):
                    return Data(data=result)

                # Handle array results from JQ query
                if isinstance(result, list):
                    return Data(data={"results": result})

                # Handle object results from JQ query
                return Data(data=result)

            # Return filtered DataFrame as list of Data objects
            records = dataframe.to_dict(orient="records")
            return Data(data={"results": records})

        except Exception as e:
            error_msg = f"Error in FilterDataComponent: {e!s}"
            raise ValueError(error_msg) from e

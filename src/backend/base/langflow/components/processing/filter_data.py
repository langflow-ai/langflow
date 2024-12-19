import json
from typing import Any

import jq
from loguru import logger

from langflow.custom import Component
from langflow.io import DataInput, IntInput, MessageTextInput, Output
from langflow.schema import Data
from langflow.schema.dataframe import DataFrame


class FilterDataComponent(Component):
    """A component for filtering data using various methods."""

    display_name = "Filter Data"
    description = "Filter data using various methods like index, JQ query, and column selection."
    icon = "filter"
    name = "FilterData"

    def __init__(self) -> None:
        """Initialize the component."""
        super().__init__()
        self.input_value: Any = None
        self.index: int | None = None
        self.jq_query: str | None = None
        self.select_columns: list[str] | None = None
        self.status: Data | None = None

    inputs = [
        DataInput(
            name="input_value",
            display_name="Input Value",
            info="The input data to filter.",
        ),
        IntInput(
            name="index",
            display_name="Index",
            info="(Optional) Index to filter (for list inputs).",
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="jq_query",
            display_name="JQ Query",
            info=(
                "(Optional) JQ query to transform the data. "
                "See https://stedolan.github.io/jq/manual/ for syntax. "
                "Example: '.[] | select(.field == \"value\")' "
                "Note: When JQ query returns a list, results will be wrapped in a 'results' field."
            ),
        ),
        MessageTextInput(
            name="select_columns",
            display_name="Select Columns",
            info="(Optional) List of column names to keep from the result. Leave empty to keep all columns.",
            is_list=True,
        ),
    ]

    outputs = [
        Output(display_name="Filtered Results", name="filtered_data", method="process_data"),
        Output(display_name="Filtered DataFrame", name="dataframe", method="process_dataframe"),
    ]

    def _parse_data(self, input_value: Data | str | dict | Any) -> str:
        """Parse input data into a string format."""
        if isinstance(input_value, Data):
            return json.dumps(input_value.data)
        if isinstance(input_value, (dict | list)):
            return json.dumps(input_value)
        if isinstance(input_value, str):
            return input_value
        return str(input_value)

    def _apply_index_filter(self, data: list, index: int) -> Any:
        """Apply index filter to list data."""
        try:
            return data[index]
        except IndexError:
            return []

    def _apply_jq_query(self, data: str, query: str) -> Any:
        """Apply JQ query to data."""
        try:
            program = jq.compile(query)
            return program.input(text=data).first()
        except ValueError as e:
            logger.exception("Error applying JQ query: %s", e)
            return data

    def _apply_column_filter(self, data: Any, columns: list[str]) -> Any:
        """Filter data by specified columns."""
        try:
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if k in columns}
            if isinstance(data, list):
                return [{k: item[k] for k in columns if k in item} for item in data]
        except (KeyError, TypeError):
            return data
        else:
            return data

    def process_dataframe(self) -> DataFrame:
        """Process data and return as DataFrame."""
        try:
            to_filter = self.input_value
            if not to_filter:
                return DataFrame()

            # Handle list input
            if isinstance(to_filter, list):
                to_filter = [self._parse_data(f) for f in to_filter]
                to_filter = f"[{','.join(to_filter)}]"
            else:
                to_filter = self._parse_data(to_filter)

            filtered_data = json.loads(to_filter)

            # Convert to DataFrame
            if isinstance(filtered_data, dict):
                filtered_frame = DataFrame([filtered_data])
            elif isinstance(filtered_data, list):
                filtered_frame = DataFrame(filtered_data)
            else:
                filtered_frame = DataFrame([{"value": filtered_data}])

            # Apply index filter if provided
            if isinstance(self.index, int) and len(filtered_frame) > 0:
                if 0 <= self.index < len(filtered_frame):
                    filtered_frame = filtered_frame.iloc[[self.index]]
                else:
                    return DataFrame()

            # Apply column filtering if needed
            if self.select_columns:
                valid_columns = [col for col in self.select_columns if col in filtered_frame.columns]
                return filtered_frame[valid_columns] if valid_columns else DataFrame()
        except (ValueError, TypeError, KeyError) as e:
            logger.exception("Error processing DataFrame: %s", e)
            return DataFrame()
        else:
            return filtered_frame

    def process_data(self) -> Data:
        """Process data and return as Data object."""
        try:
            filtered_frame = self.process_dataframe()
            if filtered_frame.empty:
                return Data(data={"results": []})
        except (ValueError, TypeError, KeyError) as e:
            error_data = Data(data={"error": str(e)})
            self.status = error_data
            logger.exception("Error processing data: %s", e)
            return error_data
        else:
            return Data(data={"results": filtered_frame.to_dict(orient="records")})

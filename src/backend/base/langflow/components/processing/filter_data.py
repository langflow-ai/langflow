import json
from typing import Any

import jq

from langflow.custom import Component
from langflow.io import DataInput, IntInput, MessageTextInput, Output
from langflow.schema import Data


class FilterDataComponent(Component):
    display_name = "Filter Data"
    description = """Extracts and filters specific elements from a Data object using a
        list of selected columns and/or a JQ query."""
    icon = "filter"
    name = "FilterData"

    inputs = [
        DataInput(
            name="input_value",
            display_name="Data",
            info="Single Data object or list of Data objects to filter",
            required=True,
            is_list=True,
        ),
        IntInput(
            name="index",
            display_name="Index",
            info="(Optional) Select a specific item by index (e.g., 0 for first item). "
            "Leave empty to keep all items.",
            advanced=True,
        ),
        MessageTextInput(
            name="select_columns",
            display_name="Select Columns",
            info="(Optional) List of column names to keep from the result. Leave empty to keep all columns.",
            is_list=True,
        ),
        MessageTextInput(
            name="jq_query",
            display_name="JQ Query",
            info=(
                "(Optional) JQ query to transform the data (e.g., '.[2]' for third item). "
                "Applied after index and before column filtering."
            ),
        ),
    ]

    outputs = [
        Output(display_name="Filtered Data", name="filtered_data", method="process_data"),
    ]

    def _parse_data(self, input_value: Data | str | dict | Any) -> str:
        """Convert input to JSON string."""
        if isinstance(input_value, Data):
            return json.dumps(input_value.data)
        if isinstance(input_value, dict):
            return json.dumps(input_value)
        if isinstance(input_value, str):
            return input_value
        return str(input_value)

    def _apply_index_filter(self, data: list[Any], index: int) -> dict | list:
        """Filter data by index."""
        try:
            if 0 <= index < len(data):
                return data[index]
        except (TypeError, IndexError):
            pass
        return data

    def _apply_jq_query(self, data: str, query: str) -> Any:
        """Apply JQ query transformation to the JSON string."""
        try:
            results = jq.compile(query).input_text(data).all()
            return results[0] if len(results) == 1 else results
        except Exception as e:
            error_message = f"Error applying JQ query: {e}"
            raise ValueError(error_message) from e

    def _apply_column_filter(
        self, data: dict[str, Any] | list[dict[str, Any]], filter_columns: list[str]
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Filter specific columns from the data."""
        if not filter_columns or not any(filter_columns):
            return data

        try:
            if isinstance(data, dict):
                return {key: value for key, value in data.items() if key in filter_columns}
            if isinstance(data, list):
                return [{key: item[key] for key in filter_columns if key in item} for item in data]
        except (KeyError, TypeError):
            return data

    def process_data(self) -> Data | list[Data]:
        """Process data in three steps: 1. Index filter, 2. JQ query, 3. Column filtering."""
        try:
            to_filter = self.input_value
            if not to_filter:
                return []

            # Handle list input
            if isinstance(to_filter, list):
                to_filter = [self._parse_data(f) for f in to_filter]
                to_filter = f"[{','.join(to_filter)}]"
            else:
                to_filter = self._parse_data(to_filter)

            filtered_data = json.loads(to_filter)

            # Step 1: Apply index filter if provided
            if isinstance(self.index, int) and isinstance(filtered_data, list):
                filtered_data = self._apply_index_filter(filtered_data, self.index)

            # Step 2: Apply JQ query if provided
            if self.jq_query and self.jq_query.strip():
                filtered_data = self._apply_jq_query(json.dumps(filtered_data), self.jq_query)

            # Step 3: Apply column filtering if needed
            if self.select_columns:
                filtered_data = self._apply_column_filter(filtered_data, self.select_columns)

            # Create result Data object(s)
            if isinstance(filtered_data, list):
                result = [
                    Data(data=item) if isinstance(item, dict | list) else Data(data={"value": item})
                    for item in filtered_data
                ]
            else:
                result = Data(
                    data=filtered_data if isinstance(filtered_data, dict | list) else {"value": filtered_data}
                )

            self.status = result
        except (ValueError, TypeError, KeyError) as e:
            error_data = Data(data={"error": str(e)})
            self.status = error_data
            error_message = f"Error processing data: {e!s}"
            raise ValueError(error_message) from e
        else:
            return result

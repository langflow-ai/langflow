import json
from typing import Any

import jq

from langflow.custom import Component
from langflow.io import DataInput, IntInput, MessageTextInput, Output
from langflow.schema import Data
from langflow.schema.dataframe import DataFrame


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
                "(Optional) JQ query to transform the data. Examples:\n"
                "- '.[0]' for first item\n"
                "- '.[] | {name, email}' for extracting specific fields\n"
                "- 'map(select(.active == true))' for filtering arrays\n"
                "Note: When JQ query returns a list, results will be wrapped in a 'results' field."
            ),
        ),
    ]

    outputs = [
        Output(display_name="Filtered Results", name="filtered_data", method="process_data"),
        Output(display_name="Filtered DataFrame", name="dataframe", method="process_dataframe"),
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

    def process_dataframe(self) -> DataFrame:
        """Process data and return as DataFrame."""
        try:
            to_filter = self.input_value
            if not to_filter:
                return DataFrame()

            # Convert input to DataFrame
            if isinstance(to_filter, list):
                if all(isinstance(x, Data) for x in to_filter):
                    filtered_frame = DataFrame(to_filter)
                else:
                    # Convert each item to Data format first
                    data_list = [
                        Data(data=item) if isinstance(item, dict) else Data(data={"value": item}) for item in to_filter
                    ]
                    filtered_frame = DataFrame(data_list)
            else:
                # Single item case
                data = self._parse_data(to_filter)
                parsed_data = json.loads(data)
                filtered_frame = DataFrame([parsed_data] if isinstance(parsed_data, dict) else [{"value": parsed_data}])

            # Apply filters
            if isinstance(self.index, int) and len(filtered_frame) > self.index:
                filtered_frame = DataFrame([filtered_frame.iloc[self.index].to_dict()])

            if self.jq_query and self.jq_query.strip():
                # Apply JQ query and convert result back to DataFrame
                json_data = filtered_frame.to_dict(orient="records")
                filtered_data = self._apply_jq_query(json.dumps(json_data), self.jq_query)
                if isinstance(filtered_data, list):
                    filtered_frame = DataFrame(filtered_data)
                else:
                    filtered_frame = DataFrame(
                        [filtered_data] if isinstance(filtered_data, dict) else [{"value": filtered_data}]
                    )

            if self.select_columns:
                filtered_frame = filtered_frame[self.select_columns]

        except Exception as e:
            error_message = f"Error processing dataframe: {e!s}"
            raise ValueError(error_message) from e
        return filtered_frame

    def process_data(self) -> Data:
        """Process data and return as Data object."""
        try:
            filtered_frame = self.process_dataframe()
            if filtered_frame.empty:
                return Data(data={})

            # Convert DataFrame result to Data format
            if len(filtered_frame) == 1:
                # Single row case
                return Data(data=filtered_frame.iloc[0].to_dict())
            # Multiple rows case
            return Data(data={"results": filtered_frame.to_dict(orient="records")})

        except Exception as e:
            error_data = Data(data={"error": str(e)})
            self.status = error_data
            error_message = f"Error processing data: {e!s}"
            raise ValueError(error_message) from e

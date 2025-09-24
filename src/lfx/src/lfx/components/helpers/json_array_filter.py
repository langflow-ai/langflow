from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, HandleInput, Output, StrInput
from lfx.schema.data import Data
from loguru import logger


class JSONArrayFilterComponent(Component):
    """Component for filtering JSON arrays based on field conditions."""

    display_name = "JSON Array Filter"
    category: str = "helpers"
    description = "Filter JSON array based on field conditions"
    documentation = "http://docs.langflow.org/components/custom"
    icon = "Filter"
    name = "json_array_filter"

    inputs = [
        HandleInput(
            name="input_array",
            display_name="Input Array",
            info="Input array of JSON objects to filter",
            required=True,
            input_types=["Data"],
            is_list=True,
        ),
        StrInput(
            name="field_name",
            display_name="Field Name",
            info="Name of the field to filter on (supports dot notation for nested fields)",
            required=True,
        ),
        DropdownInput(
            name="operator",
            display_name="Operator",
            info="Operator to use for filtering",
            options=[
                "equals",
                "not_equals",
                "contains",
                "not_contains",
                "greater_than",
                "less_than",
                "in",
                "not_in",
            ],
            value="equals",
        ),
        StrInput(
            name="value",
            display_name="Filter Value",
            info="Value to filter against",
            required=True,
        ),
        BoolInput(
            name="case_sensitive",
            display_name="Case Sensitive",
            info="Whether string comparisons should be case-sensitive",
            value=False,
        ),
        BoolInput(
            name="return_only_files",
            display_name="Return Only Files",
            info="If true, returns only array of file URLs",
            value=False,
        ),
        StrInput(
            name="file_field",
            display_name="File Field Name",
            info="Name of the field containing file URL (only used if return_only_files is true)",
            required=False,
            value="file_path",
        ),
    ]

    outputs = [
        Output(
            name="filtered_array",
            display_name="Filtered Array",
            method="filter_array",
        )
    ]

    def _compare_values(
        self,
        field_value: Any,
        filter_value: Any,
        operator: str,
        case_sensitive: bool = False,
    ) -> bool:
        """Compare two values based on the specified operator."""
        try:
            # Handle None values
            if field_value is None:
                logger.debug("Field value is None")
                return False

            # Log the types and values for debugging
            logger.debug(
                f"Comparing - Field value: {field_value} ({type(field_value)}) | Filter value: {filter_value} ({type(filter_value)})"
            )

            # Handle string comparisons with case sensitivity
            if (
                isinstance(field_value, str)
                and isinstance(filter_value, str)
                and not case_sensitive
            ):
                field_value = field_value.lower()
                filter_value = filter_value.lower()
                logger.debug(
                    f"Case-insensitive comparison: {field_value} vs {filter_value}"
                )

            if operator == "equals":
                result = field_value == filter_value
                logger.debug(f"Equals comparison result: {result}")
                return result
            if operator == "not_equals":
                return field_value != filter_value
            if operator == "contains":
                return str(filter_value) in str(field_value)
            if operator == "not_contains":
                return str(filter_value) not in str(field_value)
            if operator == "greater_than":
                return float(field_value) > float(filter_value)
            if operator == "less_than":
                return float(field_value) < float(filter_value)
            if operator == "in":
                if not isinstance(filter_value, (list, tuple)):
                    filter_value = [filter_value]
                return field_value in filter_value
            if operator == "not_in":
                if not isinstance(filter_value, (list, tuple)):
                    filter_value = [filter_value]
                return field_value not in filter_value
            logger.warning(f"Unsupported operator: {operator}")
            return False

        except (ValueError, TypeError) as e:
            logger.warning(f"Error comparing values: {e!s}")
            return False

    def _get_nested_field_value(self, obj: dict[str, Any], field_path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        try:
            current = obj
            for part in field_path.split("."):
                current = current[part]
            return current
        except (KeyError, TypeError):
            return None

    def filter_array(self) -> Data:
        """Filter the input array based on the specified conditions."""
        try:
            # Extract array from input
            if not self.input_array:
                raise ValueError("Input must not be empty")

            input_array = None
            if isinstance(self.input_array, list) and len(self.input_array) > 0:
                if isinstance(self.input_array[0], Data):
                    data_obj = self.input_array[0]
                    if isinstance(data_obj.data, dict) and "value" in data_obj.data:
                        input_array = data_obj.data["value"]
                else:
                    input_array = self.input_array
            elif isinstance(self.input_array, Data):
                if (
                    isinstance(self.input_array.data, dict)
                    and "value" in self.input_array.data
                ):
                    input_array = self.input_array.data["value"]
                else:
                    input_array = self.input_array.value

            if input_array is None:
                logger.error("Could not extract array from input")
                return Data(value=[])

            logger.debug(f"Processing array with {len(input_array)} items")

            filtered_array = []
            for item in input_array:
                if not isinstance(item, dict):
                    logger.debug(f"Skipping non-dict item: {item}")
                    continue

                field_value = self._get_nested_field_value(item, self.field_name)
                if self._compare_values(
                    field_value, self.value, self.operator, self.case_sensitive
                ):
                    filtered_array.append(item)

            logger.info(
                f"Filtered array from {len(input_array)} to {len(filtered_array)} items"
            )

            # If return_only_files is true, extract just the file URLs
            if self.return_only_files and filtered_array:
                file_field = self.file_field or "file"
                files_array = []
                for item in filtered_array:
                    file_url = self._get_nested_field_value(item, file_field)
                    if file_url:
                        files_array.append(file_url)
                logger.info(f"Extracted {len(files_array)} file URLs")
                return Data(data={"file_path": files_array})

            return Data(data={"file_path": filtered_array})

        except Exception as e:
            logger.error(f"Error filtering array: {e!s}")
            raise ValueError(f"Error filtering array: {e!s}")

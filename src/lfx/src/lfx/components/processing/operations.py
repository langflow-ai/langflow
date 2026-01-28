import ast
import contextlib
import json
import re
from typing import TYPE_CHECKING, Any

import jq
import pandas as pd
from json_repair import repair_json

from lfx.custom import Component
from lfx.field_typing import RangeSpec
from lfx.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    SortableListInput,
    StrInput,
    TabInput,
)
from lfx.io import DataFrameInput, DataInput, Output
from lfx.log.logger import logger
from lfx.schema import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

if TYPE_CHECKING:
    from collections.abc import Callable


# Operation registry: maps operation name to its configuration
OPERATIONS_BY_TYPE = {
    "Text": [
        {"name": "Word Count", "icon": "hash"},
        {"name": "Case Conversion", "icon": "type"},
        {"name": "Text Replace", "icon": "replace"},
        {"name": "Text Extract", "icon": "search"},
        {"name": "Text Head", "icon": "chevron-left"},
        {"name": "Text Tail", "icon": "chevron-right"},
        {"name": "Text Strip", "icon": "minus"},
        {"name": "Text Join", "icon": "link"},
        {"name": "Text Clean", "icon": "sparkles"},
        {"name": "Text to DataFrame", "icon": "table"},
    ],
    "Data": [
        {"name": "Select Keys", "icon": "lasso-select"},
        {"name": "Literal Eval", "icon": "braces"},
        {"name": "Combine", "icon": "merge"},
        {"name": "Filter Values", "icon": "filter"},
        {"name": "Append or Update", "icon": "circle-plus"},
        {"name": "Remove Keys", "icon": "eraser"},
        {"name": "Rename Keys", "icon": "pencil-line"},
        {"name": "Path Selection", "icon": "mouse-pointer"},
        {"name": "JQ Expression", "icon": "terminal"},
    ],
    "DataFrame": [
        {"name": "Add Column", "icon": "plus"},
        {"name": "Drop Column", "icon": "minus"},
        {"name": "Filter Rows", "icon": "filter"},
        {"name": "Head Rows", "icon": "arrow-up"},
        {"name": "Rename Column", "icon": "pencil"},
        {"name": "Replace Value", "icon": "replace"},
        {"name": "Select Columns", "icon": "columns"},
        {"name": "Sort", "icon": "arrow-up-down"},
        {"name": "Tail Rows", "icon": "arrow-down"},
        {"name": "Drop Duplicates", "icon": "copy-x"},
    ],
}

# Fields required for each operation
OPERATION_FIELDS = {
    # Text operations
    "Word Count": ["text_input", "count_words", "count_characters", "count_lines"],
    "Case Conversion": ["text_input", "case_type"],
    "Text Replace": ["text_input", "search_pattern", "replacement_text", "use_regex"],
    "Text Extract": ["text_input", "extract_pattern", "max_matches"],
    "Text Head": ["text_input", "head_characters"],
    "Text Tail": ["text_input", "tail_characters"],
    "Text Strip": ["text_input", "strip_mode", "strip_characters"],
    "Text Join": ["text_input", "text_input_2"],
    "Text Clean": ["text_input", "remove_extra_spaces", "remove_special_chars", "remove_empty_lines"],
    "Text to DataFrame": ["text_input", "table_separator", "has_header"],
    # Data operations
    "Select Keys": ["data_input", "select_keys_input"],
    "Literal Eval": ["data_input"],
    "Combine": ["data_input"],
    "Filter Values": ["data_input", "filter_key", "operator", "filter_values"],
    "Append or Update": ["data_input", "append_update_data"],
    "Remove Keys": ["data_input", "remove_keys_input"],
    "Rename Keys": ["data_input", "rename_keys_input"],
    "Path Selection": ["data_input", "mapped_json_display", "selected_key"],
    "JQ Expression": ["data_input", "query"],
    # DataFrame operations
    "Add Column": ["df_input", "new_column_name", "new_column_value"],
    "Drop Column": ["df_input", "column_name"],
    "Filter Rows": ["df_input", "column_name", "filter_value", "filter_operator"],
    "Head Rows": ["df_input", "num_rows"],
    "Rename Column": ["df_input", "column_name", "new_column_name"],
    "Replace Value": ["df_input", "column_name", "replace_value", "replacement_value"],
    "Select Columns": ["df_input", "columns_to_select"],
    "Sort": ["df_input", "column_name", "ascending"],
    "Tail Rows": ["df_input", "num_rows"],
    "Drop Duplicates": ["df_input", "column_name"],
}

# All dynamic fields that can be shown/hidden
ALL_DYNAMIC_FIELDS = [
    # Input fields
    "text_input",
    "data_input",
    "df_input",
    # Text operation fields
    "table_separator",
    "has_header",
    "count_words",
    "count_characters",
    "count_lines",
    "case_type",
    "search_pattern",
    "replacement_text",
    "use_regex",
    "extract_pattern",
    "max_matches",
    "head_characters",
    "tail_characters",
    "strip_mode",
    "strip_characters",
    "text_input_2",
    "remove_extra_spaces",
    "remove_special_chars",
    "remove_empty_lines",
    # Data operation fields
    "select_keys_input",
    "filter_key",
    "operator",
    "filter_values",
    "append_update_data",
    "remove_keys_input",
    "rename_keys_input",
    "mapped_json_display",
    "selected_key",
    "query",
    # DataFrame operation fields
    "column_name",
    "filter_value",
    "filter_operator",
    "ascending",
    "new_column_name",
    "new_column_value",
    "columns_to_select",
    "num_rows",
    "replace_value",
    "replacement_value",
]

# Data operations comparison operators
DATA_OPERATORS = {
    "equals": lambda a, b: str(a) == str(b),
    "not equals": lambda a, b: str(a) != str(b),
    "contains": lambda a, b: str(b) in str(a),
    "starts with": lambda a, b: str(a).startswith(str(b)),
    "ends with": lambda a, b: str(a).endswith(str(b)),
}

# Case converters for text operations
CASE_CONVERTERS = {
    "uppercase": str.upper,
    "lowercase": str.lower,
    "title": str.title,
    "capitalize": str.capitalize,
    "swapcase": str.swapcase,
}


class Operations(Component):
    """Unified component for Text, Data, and DataFrame operations."""

    display_name = "Operations"
    description = "Perform various operations on Text, Data, or DataFrame inputs."
    icon = "workflow"
    name = "Operations"

    inputs = [
        # Input type selection (tabs)
        TabInput(
            name="input_type",
            display_name="Input Type",
            options=["Text", "Data", "DataFrame"],
            value="Text",
            info="Select the type of input to operate on.",
            real_time_refresh=True,
        ),
        # === TEXT INPUT ===
        HandleInput(
            name="text_input",
            display_name="Text Input",
            info="The input text to process.",
            input_types=["Message"],
            show=True,
        ),
        # === DATA INPUT ===
        DataInput(
            name="data_input",
            display_name="Data",
            info="Data object to operate on.",
            is_list=True,
            show=False,
        ),
        # === DATAFRAME INPUT ===
        DataFrameInput(
            name="df_input",
            display_name="DataFrame",
            info="The input DataFrame to operate on.",
            show=False,
        ),
        # === TEXT OPERATION FIELDS ===
        StrInput(
            name="table_separator",
            display_name="Table Separator",
            info="Separator used in the table (default: '|').",
            value="|",
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="has_header",
            display_name="Has Header",
            info="Whether the table has a header row.",
            value=True,
            dynamic=True,
            advanced=True,
            show=False,
        ),
        BoolInput(
            name="count_words",
            display_name="Count Words",
            info="Include word count in analysis.",
            value=True,
            dynamic=True,
            advanced=True,
            show=False,
        ),
        BoolInput(
            name="count_characters",
            display_name="Count Characters",
            info="Include character count in analysis.",
            value=True,
            dynamic=True,
            advanced=True,
            show=False,
        ),
        BoolInput(
            name="count_lines",
            display_name="Count Lines",
            info="Include line count in analysis.",
            value=True,
            dynamic=True,
            advanced=True,
            show=False,
        ),
        DropdownInput(
            name="case_type",
            display_name="Case Type",
            options=["uppercase", "lowercase", "title", "capitalize", "swapcase"],
            value="lowercase",
            info="Type of case conversion to apply.",
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="use_regex",
            display_name="Use Regex",
            info="Whether to treat search pattern as regex.",
            value=False,
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="search_pattern",
            display_name="Search Pattern",
            info="Text pattern to search for (supports regex).",
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="replacement_text",
            display_name="Replacement Text",
            info="Text to replace the search pattern with.",
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="extract_pattern",
            display_name="Extract Pattern",
            info="Regex pattern to extract from text.",
            dynamic=True,
            show=False,
        ),
        IntInput(
            name="max_matches",
            display_name="Max Matches",
            info="Maximum number of matches to extract.",
            value=10,
            dynamic=True,
            show=False,
        ),
        IntInput(
            name="head_characters",
            display_name="Characters from Start",
            info="Number of characters to extract from the beginning of text.",
            value=100,
            dynamic=True,
            show=False,
            range_spec=RangeSpec(min=0, max=1000000, step=1, step_type="int"),
        ),
        IntInput(
            name="tail_characters",
            display_name="Characters from End",
            info="Number of characters to extract from the end of text.",
            value=100,
            dynamic=True,
            show=False,
            range_spec=RangeSpec(min=0, max=1000000, step=1, step_type="int"),
        ),
        DropdownInput(
            name="strip_mode",
            display_name="Strip Mode",
            options=["both", "left", "right"],
            value="both",
            info="Which sides to strip whitespace from.",
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="strip_characters",
            display_name="Characters to Strip",
            info="Specific characters to remove (leave empty for whitespace).",
            value="",
            dynamic=True,
            show=False,
        ),
        HandleInput(
            name="text_input_2",
            display_name="Second Text Input",
            info="Second text to join with the first text.",
            input_types=["Message"],
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="remove_extra_spaces",
            display_name="Remove Extra Spaces",
            info="Remove multiple consecutive spaces.",
            value=True,
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="remove_special_chars",
            display_name="Remove Special Characters",
            info="Remove special characters except alphanumeric and spaces.",
            value=False,
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="remove_empty_lines",
            display_name="Remove Empty Lines",
            info="Remove empty lines from text.",
            value=False,
            dynamic=True,
            show=False,
        ),
        # === DATA OPERATION FIELDS ===
        MessageTextInput(
            name="select_keys_input",
            display_name="Select Keys",
            info="List of keys to select from the data.",
            show=False,
            is_list=True,
        ),
        MessageTextInput(
            name="filter_key",
            display_name="Filter Key",
            info="Name of the key containing the list to filter.",
            is_list=True,
            show=False,
        ),
        DropdownInput(
            name="operator",
            display_name="Comparison Operator",
            options=["equals", "not equals", "contains", "starts with", "ends with"],
            info="The operator to apply for comparing the values.",
            value="equals",
            show=False,
        ),
        DictInput(
            name="filter_values",
            display_name="Filter Values",
            info="Key-value pairs to filter by.",
            show=False,
            is_list=True,
        ),
        DictInput(
            name="append_update_data",
            display_name="Append or Update",
            info="Data to append or update the existing data with.",
            show=False,
            value={"key": "value"},
            is_list=True,
        ),
        MessageTextInput(
            name="remove_keys_input",
            display_name="Remove Keys",
            info="List of keys to remove from the data.",
            show=False,
            is_list=True,
        ),
        DictInput(
            name="rename_keys_input",
            display_name="Rename Keys",
            info="Mapping of old keys to new keys.",
            show=False,
            is_list=True,
            value={"old_key": "new_key"},
        ),
        MultilineInput(
            name="mapped_json_display",
            display_name="JSON to Map",
            info="Paste JSON here to explore its structure and select a path.",
            required=False,
            refresh_button=True,
            real_time_refresh=True,
            placeholder="Add a JSON example.",
            show=False,
        ),
        DropdownInput(
            name="selected_key",
            display_name="Select Path",
            options=[],
            required=False,
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="query",
            display_name="JQ Expression",
            info="JQ expression to query the data.",
            placeholder="e.g., .properties.id",
            show=False,
        ),
        # === DATAFRAME OPERATION FIELDS ===
        StrInput(
            name="column_name",
            display_name="Column Name",
            info="The column name to use for the operation.",
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="filter_value",
            display_name="Filter Value",
            info="The value to filter rows by.",
            dynamic=True,
            show=False,
        ),
        DropdownInput(
            name="filter_operator",
            display_name="Filter Operator",
            options=[
                "equals",
                "not equals",
                "contains",
                "not contains",
                "starts with",
                "ends with",
                "greater than",
                "less than",
            ],
            value="equals",
            info="The operator to apply for filtering rows.",
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="ascending",
            display_name="Sort Ascending",
            info="Whether to sort in ascending order.",
            dynamic=True,
            show=False,
            value=True,
        ),
        StrInput(
            name="new_column_name",
            display_name="New Column Name",
            info="The new column name when renaming or adding a column.",
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="new_column_value",
            display_name="New Column Value",
            info="The value to populate the new column with.",
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="columns_to_select",
            display_name="Columns to Select",
            dynamic=True,
            is_list=True,
            show=False,
        ),
        IntInput(
            name="num_rows",
            display_name="Number of Rows",
            info="Number of rows to return.",
            dynamic=True,
            show=False,
            value=5,
        ),
        MessageTextInput(
            name="replace_value",
            display_name="Value to Replace",
            info="The value to replace in the column.",
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="replacement_value",
            display_name="Replacement Value",
            info="The value to replace with.",
            dynamic=True,
            show=False,
        ),
        # === OPERATION SELECTION (last) ===
        SortableListInput(
            name="operation",
            display_name="Operation",
            placeholder="Select Operation",
            info="Select the operation to perform.",
            options=OPERATIONS_BY_TYPE["Text"],  # Default to Text operations
            real_time_refresh=True,
            limit=1,
        ),
    ]

    outputs = []

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update build configuration based on input type and operation selection."""
        # Hide all dynamic fields first
        for field in ALL_DYNAMIC_FIELDS:
            if field in build_config:
                build_config[field]["show"] = False

        # Handle input_type change - update operation options
        if field_name == "input_type":
            input_type = field_value
            build_config["operation"]["options"] = OPERATIONS_BY_TYPE.get(input_type, [])
            build_config["operation"]["value"] = []  # Clear selection when type changes

            # Show the appropriate input field
            if input_type == "Text":
                build_config["text_input"]["show"] = True
            elif input_type == "Data":
                build_config["data_input"]["show"] = True
                # Set is_list based on operation (default to False)
                build_config["data_input"]["is_list"] = False
            elif input_type == "DataFrame":
                build_config["df_input"]["show"] = True

            return build_config

        # Handle operation change - show relevant fields
        if field_name == "operation":
            operation_name = self._extract_operation_name(field_value)
            if not operation_name:
                # Still show the input field based on current input_type
                input_type = build_config.get("input_type", {}).get("value", "Text")
                if input_type == "Text":
                    build_config["text_input"]["show"] = True
                elif input_type == "Data":
                    build_config["data_input"]["show"] = True
                elif input_type == "DataFrame":
                    build_config["df_input"]["show"] = True
                return build_config

            # Get fields for this operation
            fields_to_show = OPERATION_FIELDS.get(operation_name, [])
            for field in fields_to_show:
                if field in build_config:
                    build_config[field]["show"] = True

            # Special handling for Data operations that need is_list=True
            if operation_name == "Combine":
                build_config["data_input"]["is_list"] = True
            elif "data_input" in fields_to_show:
                build_config["data_input"]["is_list"] = False

            return build_config

        # Handle mapped_json_display change for Path Selection
        if field_name == "mapped_json_display":
            try:
                parsed_json = json.loads(field_value)
                keys = self._extract_all_paths(parsed_json)
                build_config["selected_key"]["options"] = keys
                build_config["selected_key"]["show"] = True
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.error(f"Error parsing mapped JSON: {e}")
                build_config["selected_key"]["show"] = False

        # Preserve current visibility state for fields not being changed
        if field_name not in ("input_type", "operation"):
            input_type = build_config.get("input_type", {}).get("value", "Text")
            operation_value = build_config.get("operation", {}).get("value", [])
            operation_name = self._extract_operation_name(operation_value)

            # Show input field
            if input_type == "Text":
                build_config["text_input"]["show"] = True
            elif input_type == "Data":
                build_config["data_input"]["show"] = True
            elif input_type == "DataFrame":
                build_config["df_input"]["show"] = True

            # Show operation fields
            if operation_name:
                fields_to_show = OPERATION_FIELDS.get(operation_name, [])
                for field in fields_to_show:
                    if field in build_config:
                        build_config[field]["show"] = True

        return build_config

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Create dynamic outputs based on selected operation."""
        # Always update outputs when input_type or operation changes
        # Also update when operation-related fields change (for Path Selection, etc.)
        if field_name not in ("input_type", "operation", "mapped_json_display", "selected_key"):
            return frontend_node

        frontend_node["outputs"] = []

        # Get current input type and operation
        input_type = None
        operation_name = None

        if field_name == "input_type":
            input_type = field_value
            # When input type changes, no operation is selected yet
            operation_name = None
        elif field_name == "operation":
            operation_name = self._extract_operation_name(field_value)
            # Get input_type from the node template
            input_type = frontend_node.get("template", {}).get("input_type", {}).get("value", "Text")
        else:
            # For other fields (mapped_json_display, selected_key), get current values from template
            operation_value = frontend_node.get("template", {}).get("operation", {}).get("value", [])
            operation_name = self._extract_operation_name(operation_value)
            input_type = frontend_node.get("template", {}).get("input_type", {}).get("value", "Text")

        # If no operation selected, show default output based on input type
        if not operation_name:
            if input_type == "Text":
                frontend_node["outputs"].append(Output(display_name="Message", name="message", method="get_message"))
            elif input_type == "Data":
                frontend_node["outputs"].append(Output(display_name="Data", name="data_output", method="get_data"))
            elif input_type == "DataFrame":
                frontend_node["outputs"].append(
                    Output(display_name="DataFrame", name="dataframe", method="get_dataframe")
                )
            return frontend_node

        # First, explicitly check for Path Selection to ensure it always gets output
        if operation_name == "Path Selection":
            frontend_node["outputs"].append(Output(display_name="Data", name="data_output", method="get_data"))
            return frontend_node

        # Then check if it's a Data operation by checking OPERATION_FIELDS
        # This ensures all Data operations get the correct output
        if operation_name in OPERATION_FIELDS and "data_input" in OPERATION_FIELDS.get(operation_name, []):
            frontend_node["outputs"].append(Output(display_name="Data", name="data_output", method="get_data"))
            return frontend_node

        # Text operations outputs
        if operation_name == "Word Count":
            frontend_node["outputs"].append(Output(display_name="Data", name="data_output", method="get_data"))
        elif operation_name == "Text to DataFrame":
            frontend_node["outputs"].append(Output(display_name="DataFrame", name="dataframe", method="get_dataframe"))
        elif operation_name == "Text Join":
            frontend_node["outputs"].append(Output(display_name="Text", name="text", method="get_text"))
            frontend_node["outputs"].append(Output(display_name="Message", name="message", method="get_message"))
        elif operation_name in (
            "Case Conversion",
            "Text Replace",
            "Text Extract",
            "Text Head",
            "Text Tail",
            "Text Strip",
            "Text Clean",
        ):
            frontend_node["outputs"].append(Output(display_name="Message", name="message", method="get_message"))
        # DataFrame operations outputs
        elif operation_name in OPERATION_FIELDS and "df_input" in OPERATION_FIELDS.get(operation_name, []):
            frontend_node["outputs"].append(Output(display_name="DataFrame", name="dataframe", method="get_dataframe"))
        # Final fallback: use input_type to determine output
        elif not frontend_node["outputs"]:
            if input_type == "Text":
                frontend_node["outputs"].append(Output(display_name="Message", name="message", method="get_message"))
            elif input_type == "Data":
                frontend_node["outputs"].append(Output(display_name="Data", name="data_output", method="get_data"))
            elif input_type == "DataFrame":
                frontend_node["outputs"].append(
                    Output(display_name="DataFrame", name="dataframe", method="get_dataframe")
                )

        return frontend_node

    def _extract_operation_name(self, field_value: Any) -> str:
        """Extract operation name from SortableListInput value."""
        if isinstance(field_value, list) and len(field_value) > 0:
            return field_value[0].get("name", "")
        return ""

    def get_operation_name(self) -> str:
        """Get the selected operation name."""
        operation_input = getattr(self, "operation", [])
        return self._extract_operation_name(operation_input)

    # ==================== OUTPUT METHODS ====================

    def get_message(self) -> Message:
        """Return result as Message."""
        result = self._process()
        return Message(text=self._format_result_as_text(result))

    def get_text(self) -> Message:
        """Return result as Message (text output)."""
        result = self._process()
        return Message(text=self._format_result_as_text(result))

    def get_data(self) -> Data:
        """Return result as Data object."""
        result = self._process()
        if result is None:
            return Data(data={})
        if isinstance(result, Data):
            return result
        if isinstance(result, dict):
            return Data(data=result)
        if isinstance(result, list):
            return Data(data={"items": result})
        return Data(data={"result": str(result)})

    def get_dataframe(self) -> DataFrame:
        """Return result as DataFrame."""
        result = self._process()
        if result is None:
            return DataFrame(pd.DataFrame())
        if isinstance(result, DataFrame):
            return result
        if isinstance(result, pd.DataFrame):
            return DataFrame(result)
        return DataFrame(pd.DataFrame())

    def _format_result_as_text(self, result: Any) -> str:
        """Format result as text string."""
        if result is None:
            return ""
        if isinstance(result, list):
            return "\n".join(str(item) for item in result)
        if isinstance(result, dict):
            return json.dumps(result, indent=2)
        return str(result)

    def _process(self) -> Any:
        """Process based on the selected operation."""
        operation = self.get_operation_name()
        if not operation:
            return None

        # Text operations
        text_handlers = {
            "Word Count": self._word_count,
            "Case Conversion": self._case_conversion,
            "Text Replace": self._text_replace,
            "Text Extract": self._text_extract,
            "Text Head": self._text_head,
            "Text Tail": self._text_tail,
            "Text Strip": self._text_strip,
            "Text Join": self._text_join,
            "Text Clean": self._text_clean,
            "Text to DataFrame": self._text_to_dataframe,
        }

        # Data operations
        data_handlers: dict[str, Callable[[], Data]] = {
            "Select Keys": self._select_keys,
            "Literal Eval": self._evaluate_data,
            "Combine": self._combine_data,
            "Filter Values": self._multi_filter_data,
            "Append or Update": self._append_update,
            "Remove Keys": self._remove_keys,
            "Rename Keys": self._rename_keys,
            "Path Selection": self._json_path,
            "JQ Expression": self._json_query,
        }

        # DataFrame operations
        df_handlers = {
            "Add Column": self._df_add_column,
            "Drop Column": self._df_drop_column,
            "Filter Rows": self._df_filter_rows,
            "Head Rows": self._df_head,
            "Rename Column": self._df_rename_column,
            "Replace Value": self._df_replace_value,
            "Select Columns": self._df_select_columns,
            "Sort": self._df_sort,
            "Tail Rows": self._df_tail,
            "Drop Duplicates": self._df_drop_duplicates,
        }

        # Try each handler category
        if operation in text_handlers:
            return text_handlers[operation]()
        if operation in data_handlers:
            return data_handlers[operation]()
        if operation in df_handlers:
            return df_handlers[operation]()

        return None

    # ==================== TEXT OPERATIONS ====================

    def _extract_text(self, value: Any) -> str:
        """Extract text from a value, handling both string and Message types."""
        if value is None:
            return ""
        if hasattr(value, "text"):
            return str(value.text) if value.text else ""
        return str(value)

    def _get_text_input(self) -> str:
        """Get text from text_input."""
        return self._extract_text(getattr(self, "text_input", ""))

    def _word_count(self) -> dict[str, Any]:
        """Count words, characters, and lines in text."""
        text_str = self._get_text_input()
        is_empty = not text_str or not text_str.strip()
        result: dict[str, Any] = {}

        if getattr(self, "count_words", True):
            if is_empty:
                result["word_count"] = 0
                result["unique_words"] = 0
            else:
                words = text_str.split()
                result["word_count"] = len(words)
                result["unique_words"] = len(set(words))

        if getattr(self, "count_characters", True):
            if is_empty:
                result["character_count"] = 0
                result["character_count_no_spaces"] = 0
            else:
                result["character_count"] = len(text_str)
                result["character_count_no_spaces"] = len(text_str.replace(" ", ""))

        if getattr(self, "count_lines", True):
            if is_empty:
                result["line_count"] = 0
                result["non_empty_lines"] = 0
            else:
                lines = text_str.split("\n")
                result["line_count"] = len(lines)
                result["non_empty_lines"] = len([line for line in lines if line.strip()])

        return result

    def _case_conversion(self) -> str:
        """Convert text case."""
        text = self._get_text_input()
        case_type = getattr(self, "case_type", "lowercase")
        converter = CASE_CONVERTERS.get(case_type)
        return converter(text) if converter else text

    def _text_replace(self) -> str:
        """Replace text patterns."""
        text = self._get_text_input()
        search_pattern = getattr(self, "search_pattern", "")
        if not search_pattern:
            return text

        replacement_text = getattr(self, "replacement_text", "")
        use_regex = getattr(self, "use_regex", False)

        if use_regex:
            try:
                return re.sub(search_pattern, replacement_text, text)
            except re.error as e:
                self.log(f"Invalid regex pattern: {e}")
                return text

        return text.replace(search_pattern, replacement_text)

    def _text_extract(self) -> list[str]:
        """Extract text matching patterns."""
        text = self._get_text_input()
        extract_pattern = getattr(self, "extract_pattern", "")
        if not extract_pattern:
            return []

        max_matches = getattr(self, "max_matches", 10)

        try:
            matches = re.findall(extract_pattern, text)
        except re.error as e:
            msg = f"Invalid regex pattern '{extract_pattern}': {e}"
            raise ValueError(msg) from e

        return matches[:max_matches] if max_matches > 0 else matches

    def _text_head(self) -> str:
        """Extract characters from the beginning of text."""
        text = self._get_text_input()
        head_characters = getattr(self, "head_characters", 100)
        if head_characters < 0:
            msg = f"Characters from Start must be non-negative, got {head_characters}"
            raise ValueError(msg)
        return text[:head_characters] if head_characters > 0 else ""

    def _text_tail(self) -> str:
        """Extract characters from the end of text."""
        text = self._get_text_input()
        tail_characters = getattr(self, "tail_characters", 100)
        if tail_characters < 0:
            msg = f"Characters from End must be non-negative, got {tail_characters}"
            raise ValueError(msg)
        return text[-tail_characters:] if tail_characters > 0 else ""

    def _text_strip(self) -> str:
        """Remove whitespace or specific characters from text edges."""
        text = self._get_text_input()
        strip_mode = getattr(self, "strip_mode", "both")
        strip_characters = getattr(self, "strip_characters", "")
        chars_to_strip = strip_characters if strip_characters else None

        if strip_mode == "left":
            return text.lstrip(chars_to_strip)
        if strip_mode == "right":
            return text.rstrip(chars_to_strip)
        return text.strip(chars_to_strip)

    def _text_join(self) -> str:
        """Join two texts with line break separator."""
        text1 = self._get_text_input()
        text2 = self._extract_text(getattr(self, "text_input_2", ""))

        if text1 and text2:
            return f"{text1}\n{text2}"
        return text1 or text2

    def _text_clean(self) -> str:
        """Clean text by removing extra spaces, special chars, etc."""
        text = self._get_text_input()
        result = text

        if getattr(self, "remove_extra_spaces", True):
            result = re.sub(r"\s+", " ", result)

        if getattr(self, "remove_special_chars", False):
            result = re.sub(r"[^\w\s]", "", result)

        if getattr(self, "remove_empty_lines", False):
            lines = [line for line in result.split("\n") if line.strip()]
            result = "\n".join(lines)

        return result

    def _text_to_dataframe(self) -> DataFrame:
        """Convert markdown-style table text to DataFrame."""
        text = self._get_text_input()
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        if not lines:
            return DataFrame(pd.DataFrame())

        separator = getattr(self, "table_separator", "|")
        has_header = getattr(self, "has_header", True)

        rows = []
        for line in lines:
            cleaned_line = line.strip(separator)
            cells = [cell.strip() for cell in cleaned_line.split(separator)]
            rows.append(cells)

        if not rows:
            return DataFrame(pd.DataFrame())

        if has_header and len(rows) > 1:
            header = rows[0]
            data_rows = rows[1:]
            df = pd.DataFrame(data_rows, columns=header)
        else:
            max_cols = max(len(row) for row in rows) if rows else 0
            columns = [f"col_{i}" for i in range(max_cols)]
            df = pd.DataFrame(rows, columns=columns)

        # Convert numeric columns
        for col in df.columns:
            with contextlib.suppress(ValueError, TypeError):
                df[col] = pd.to_numeric(df[col])

        self.log(f"Converted text to DataFrame: {len(df)} rows, {len(df.columns)} columns")
        return DataFrame(df)

    # ==================== DATA OPERATIONS ====================

    def _get_data_dict(self) -> dict:
        """Extract data dictionary from Data object."""
        data = self.data_input
        if isinstance(data, list) and len(data) == 1:
            data = data[0]
        return data.model_dump() if hasattr(data, "model_dump") else {}

    def _get_normalized_data(self) -> dict:
        """Get normalized data dictionary, handling the 'data' key if present."""
        data_dict = self._get_data_dict()
        return data_dict.get("data", data_dict)

    def _data_is_list(self) -> bool:
        """Check if data contains multiple items."""
        data = getattr(self, "data_input", None)
        return isinstance(data, list) and len(data) > 1

    def _validate_single_data(self, operation: str) -> None:
        """Validate that the operation is being performed on a single data object."""
        if self._data_is_list():
            msg = f"{operation} operation is not supported for multiple data objects."
            raise ValueError(msg)

    def _select_keys(self) -> Data:
        """Select specific keys from the data dictionary."""
        self._validate_single_data("Select Keys")
        data_dict = self._get_normalized_data()
        filter_criteria: list[str] = getattr(self, "select_keys_input", [])

        if len(filter_criteria) == 1 and filter_criteria[0] == "data":
            filtered = data_dict["data"]
        else:
            if not all(key in data_dict for key in filter_criteria):
                msg = f"Select key not found in data. Available keys: {list(data_dict.keys())}"
                raise ValueError(msg)
            filtered = {key: value for key, value in data_dict.items() if key in filter_criteria}

        return Data(data=filtered)

    def _evaluate_data(self) -> Data:
        """Evaluate string values in the data dictionary."""
        self._validate_single_data("Literal Eval")
        return Data(**self._recursive_eval(self._get_data_dict()))

    def _recursive_eval(self, data: Any) -> Any:
        """Recursively evaluate string values."""
        if isinstance(data, dict):
            return {k: self._recursive_eval(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._recursive_eval(item) for item in data]
        if isinstance(data, str):
            try:
                if (
                    data.strip().startswith(("{", "[", "(", "'", '"'))
                    or data.strip().lower() in ("true", "false", "none")
                    or data.strip().replace(".", "").isdigit()
                ):
                    return ast.literal_eval(data)
            except (ValueError, SyntaxError, TypeError, MemoryError):
                return data
            else:
                return data
        return data

    def _combine_data(self) -> Data:
        """Combine multiple data objects into one."""
        data = getattr(self, "data_input", [])
        if not self._data_is_list():
            return data[0] if data else Data(data={})

        data_dicts = [d.model_dump().get("data", d.model_dump()) for d in data]
        combined_data = {}

        for data_dict in data_dicts:
            for key, value in data_dict.items():
                if key not in combined_data:
                    combined_data[key] = value
                elif isinstance(combined_data[key], list):
                    if isinstance(value, list):
                        combined_data[key].extend(value)
                    else:
                        combined_data[key].append(value)
                else:
                    combined_data[key] = (
                        [combined_data[key], value] if not isinstance(value, list) else [combined_data[key], *value]
                    )

        return Data(**combined_data)

    def _multi_filter_data(self) -> Data:
        """Apply multiple filters to the data."""
        self._validate_single_data("Filter Values")
        data_filtered = self._get_normalized_data()
        filter_key_list = getattr(self, "filter_key", [])
        filter_values_dict = getattr(self, "filter_values", {})
        operator = getattr(self, "operator", "equals")

        for filter_key in filter_key_list:
            if filter_key not in data_filtered:
                msg = f"Filter key '{filter_key}' not found in data. Available keys: {list(data_filtered.keys())}"
                raise ValueError(msg)

            if isinstance(data_filtered[filter_key], list):
                for filter_data_key, filter_value in filter_values_dict.items():
                    if filter_value is not None:
                        filtered_list = []
                        for item in data_filtered[filter_key]:
                            if isinstance(item, dict) and filter_data_key in item:
                                comparison_func = DATA_OPERATORS.get(operator)
                                if comparison_func and comparison_func(item[filter_data_key], filter_value):
                                    filtered_list.append(item)
                        data_filtered[filter_key] = filtered_list
            else:
                msg = f"Filter key '{filter_key}' is not a list."
                raise TypeError(msg)

        return Data(**data_filtered)

    def _append_update(self) -> Data:
        """Append or Update with new key-value pairs."""
        self._validate_single_data("Append or Update")
        data_filtered = self._get_normalized_data()
        append_data = getattr(self, "append_update_data", {})

        for key, value in append_data.items():
            data_filtered[key] = value

        return Data(**data_filtered)

    def _remove_keys(self) -> Data:
        """Remove specified keys from the data dictionary, recursively."""
        self._validate_single_data("Remove Keys")
        data_dict = self._get_normalized_data()
        remove_keys = set(getattr(self, "remove_keys_input", []))

        def remove_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: remove_recursive(v) for k, v in obj.items() if k not in remove_keys}
            if isinstance(obj, list):
                return [remove_recursive(item) for item in obj]
            return obj

        return Data(data=remove_recursive(data_dict))

    def _rename_keys(self) -> Data:
        """Rename keys in the data dictionary, recursively."""
        self._validate_single_data("Rename Keys")
        data_dict = self._get_normalized_data()
        rename_map = getattr(self, "rename_keys_input", {})

        def rename_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {rename_map.get(k, k): rename_recursive(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [rename_recursive(item) for item in obj]
            return obj

        return Data(data=rename_recursive(data_dict))

    def _json_path(self) -> Data:
        """Select data by JSON path."""
        try:
            data = getattr(self, "data_input", None)
            selected_key = getattr(self, "selected_key", None)
            if not data or not selected_key:
                msg = "Missing input data or selected key."
                raise ValueError(msg)
            input_payload = data[0].data if isinstance(data, list) else data.data
            compiled = jq.compile(selected_key)
            result = compiled.input(input_payload).first()
            if isinstance(result, dict):
                return Data(data=result)
            return Data(data={"result": result})
        except (ValueError, TypeError, KeyError) as e:
            self.status = f"Error: {e!s}"
            self.log(self.status)
            return Data(data={"error": str(e)})

    def _json_query(self) -> Data:
        """Query data using JQ expression."""
        query = getattr(self, "query", "")
        if not query or not query.strip():
            msg = "JQ Expression is required and cannot be blank."
            raise ValueError(msg)

        raw_data = self._get_data_dict()
        try:
            input_str = json.dumps(raw_data)
            repaired = repair_json(input_str)
            data_json = json.loads(repaired)
            jq_input = data_json["data"] if isinstance(data_json, dict) and "data" in data_json else data_json
            results = jq.compile(query).input(jq_input).all()
            if not results:
                msg = "No result from JQ query."
                raise ValueError(msg)
            result = results[0] if len(results) == 1 else results
            if result is None or result == "None":
                msg = "JQ query returned null/None. Check if the path exists in your data."
                raise ValueError(msg)
            if isinstance(result, dict):
                return Data(data=result)
            return Data(data={"result": result})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            logger.error(f"JQ Query failed: {e}")
            msg = f"JQ Query error: {e}"
            raise ValueError(msg) from e

    @staticmethod
    def _extract_all_paths(obj: Any, path: str = "") -> list[str]:
        """Extract all JSON paths from an object."""
        paths = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_path = f"{path}.{k}" if path else f".{k}"
                paths.append(new_path)
                paths.extend(Operations._extract_all_paths(v, new_path))
        elif isinstance(obj, list) and obj:
            new_path = f"{path}[0]"
            paths.append(new_path)
            paths.extend(Operations._extract_all_paths(obj[0], new_path))
        return paths

    # ==================== DATAFRAME OPERATIONS ====================

    def _get_df(self) -> pd.DataFrame:
        """Get the input DataFrame."""
        df = getattr(self, "df_input", None)
        if df is None:
            return pd.DataFrame()
        if isinstance(df, DataFrame):
            return df.copy()
        if isinstance(df, pd.DataFrame):
            return df.copy()
        return pd.DataFrame()

    def _df_add_column(self) -> DataFrame:
        """Add a new column to the DataFrame."""
        df = self._get_df()
        new_column_name = getattr(self, "new_column_name", "")
        new_column_value = getattr(self, "new_column_value", "")
        df[new_column_name] = [new_column_value] * len(df)
        return DataFrame(df)

    def _df_drop_column(self) -> DataFrame:
        """Drop a column from the DataFrame."""
        df = self._get_df()
        column_name = getattr(self, "column_name", "")
        return DataFrame(df.drop(columns=[column_name]))

    def _df_filter_rows(self) -> DataFrame:
        """Filter rows by value."""
        df = self._get_df()
        column_name = getattr(self, "column_name", "")
        filter_value = getattr(self, "filter_value", "")
        operator = getattr(self, "filter_operator", "equals")

        column = df[column_name]

        if operator == "equals":
            mask = column == filter_value
        elif operator == "not equals":
            mask = column != filter_value
        elif operator == "contains":
            mask = column.astype(str).str.contains(str(filter_value), na=False)
        elif operator == "not contains":
            mask = ~column.astype(str).str.contains(str(filter_value), na=False)
        elif operator == "starts with":
            mask = column.astype(str).str.startswith(str(filter_value), na=False)
        elif operator == "ends with":
            mask = column.astype(str).str.endswith(str(filter_value), na=False)
        elif operator == "greater than":
            try:
                numeric_value = pd.to_numeric(filter_value)
                mask = column > numeric_value
            except (ValueError, TypeError):
                mask = column.astype(str) > str(filter_value)
        elif operator == "less than":
            try:
                numeric_value = pd.to_numeric(filter_value)
                mask = column < numeric_value
            except (ValueError, TypeError):
                mask = column.astype(str) < str(filter_value)
        else:
            mask = column == filter_value

        return DataFrame(df[mask])

    def _df_head(self) -> DataFrame:
        """Get the first N rows."""
        df = self._get_df()
        num_rows = getattr(self, "num_rows", 5)
        return DataFrame(df.head(num_rows))

    def _df_tail(self) -> DataFrame:
        """Get the last N rows."""
        df = self._get_df()
        num_rows = getattr(self, "num_rows", 5)
        return DataFrame(df.tail(num_rows))

    def _df_rename_column(self) -> DataFrame:
        """Rename a column."""
        df = self._get_df()
        column_name = getattr(self, "column_name", "")
        new_column_name = getattr(self, "new_column_name", "")
        return DataFrame(df.rename(columns={column_name: new_column_name}))

    def _df_replace_value(self) -> DataFrame:
        """Replace values in a column."""
        df = self._get_df()
        column_name = getattr(self, "column_name", "")
        replace_value = getattr(self, "replace_value", "")
        replacement_value = getattr(self, "replacement_value", "")
        df[column_name] = df[column_name].replace(replace_value, replacement_value)
        return DataFrame(df)

    def _df_select_columns(self) -> DataFrame:
        """Select specific columns."""
        df = self._get_df()
        columns = [col.strip() for col in getattr(self, "columns_to_select", [])]
        return DataFrame(df[columns])

    def _df_sort(self) -> DataFrame:
        """Sort by column."""
        df = self._get_df()
        column_name = getattr(self, "column_name", "")
        ascending = getattr(self, "ascending", True)
        return DataFrame(df.sort_values(by=column_name, ascending=ascending))

    def _df_drop_duplicates(self) -> DataFrame:
        """Drop duplicate rows based on a column."""
        df = self._get_df()
        column_name = getattr(self, "column_name", "")
        return DataFrame(df.drop_duplicates(subset=column_name))

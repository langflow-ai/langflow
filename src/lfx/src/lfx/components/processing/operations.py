"""Unified Operations component.

Brings together the previously separate JSON, Table, and Text operation
components into a single component. An "Input Type" selector (Text / JSON /
Table) drives everything: it filters the "Operation" picker to the operations
that apply to that type, reveals the matching input (Text / JSON / Table) and
its operation-specific fields, and advertises the appropriate output type.

The three original components (JSON Operations, Table Operations, Text
Operations) remain available as legacy components for backward compatibility
with existing flows.
"""

import ast
import contextlib
import json
import re
from typing import TYPE_CHECKING, Any

import pandas as pd
from json_repair import repair_json

from lfx.custom import Component
from lfx.field_typing import RangeSpec
from lfx.inputs import DictInput, SortableListInput, TabInput
from lfx.io import (
    BoolInput,
    DataFrameInput,
    DataInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    StrInput,
)
from lfx.log.logger import logger
from lfx.schema import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message

if TYPE_CHECKING:
    from collections.abc import Callable

# The "Input Type" selector tabs. Each value maps a Langflow data type to the
# operations, input, and output that belong to it.
INPUT_TYPES = ["Text", "JSON", "Table"]

# Operations grouped by input type, in display order, each with the icon shown
# in the Operation picker. This is the single source of truth for the picker;
# update_build_config swaps the picker's options to the selected type's list.
OPERATIONS_BY_TYPE: dict[str, list[dict[str, str]]] = {
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
    "JSON": [
        {"name": "Select Keys", "icon": "lasso-select"},
        {"name": "Literal Eval", "icon": "braces"},
        {"name": "Combine", "icon": "merge"},
        {"name": "Append or Update", "icon": "circle-plus"},
        {"name": "Remove Keys", "icon": "eraser"},
        {"name": "Rename Keys", "icon": "pencil-line"},
        {"name": "Path Selection", "icon": "mouse-pointer"},
        {"name": "JQ Expression", "icon": "terminal"},
    ],
    "Table": [
        {"name": "Add Column", "icon": "plus"},
        {"name": "Concatenate", "icon": "combine"},
        {"name": "Drop Column", "icon": "minus"},
        {"name": "Filter", "icon": "filter"},
        {"name": "Head", "icon": "arrow-up"},
        {"name": "Merge", "icon": "merge"},
        {"name": "Rename Column", "icon": "pencil"},
        {"name": "Replace Value", "icon": "replace"},
        {"name": "Select Columns", "icon": "columns"},
        {"name": "Sort", "icon": "arrow-up-down"},
        {"name": "Tail", "icon": "arrow-down"},
        {"name": "Drop Duplicates", "icon": "copy-x"},
    ],
}

# Operation-name sets derived from the picker, used for dispatch and output
# routing. Keeping them derived from OPERATIONS_BY_TYPE avoids any drift.
JSON_OPERATIONS = {op["name"] for op in OPERATIONS_BY_TYPE["JSON"]}
TABLE_OPERATIONS = {op["name"] for op in OPERATIONS_BY_TYPE["Table"]}
TEXT_OPERATIONS = {op["name"] for op in OPERATIONS_BY_TYPE["Text"]}

# Each input type maps to its main input field and its default output. "Text"
# normally outputs a Message; "JSON" a Data; "Table" a DataFrame. A few text
# operations override this (Word Count -> Data, Text to DataFrame -> DataFrame).
INPUT_TYPE_TO_MAIN_INPUT = {"Text": "text_input", "JSON": "data", "Table": "df"}

# Case conversions for the Text "Case Conversion" operation.
CASE_CONVERTERS: dict[str, Any] = {
    "uppercase": str.upper,
    "lowercase": str.lower,
    "title": str.title,
    "capitalize": str.capitalize,
    "swapcase": str.swapcase,
}


class OperationsComponent(Component):
    display_name = "Operations"
    description = "Perform operations on Text, JSON, and Tables from a single component."
    documentation: str = "https://docs.langflow.org/components-processing#operations"
    icon = "wand-sparkles"
    name = "Operations"
    metadata = {
        "keywords": [
            "operations",
            "data operations",
            "json",
            "json operations",
            "table",
            "table operations",
            "dataframe",
            "dataframe operations",
            "text",
            "text operations",
            "select keys",
            "literal eval",
            "combine",
            "append or update",
            "remove keys",
            "rename keys",
            "path selection",
            "jq expression",
            "parse json",
            "add column",
            "concatenate",
            "drop column",
            "filter",
            "head",
            "merge",
            "rename column",
            "replace value",
            "select columns",
            "sort",
            "tail",
            "drop duplicates",
            "word count",
            "case conversion",
            "text replace",
            "text extract",
            "text join",
            "text clean",
            "text to dataframe",
            "data manipulation",
            "data transformation",
        ],
    }

    # Operation -> operation-specific input fields to reveal when selected.
    OPERATION_FIELDS: dict[str, list[str]] = {
        # JSON
        "Select Keys": ["select_keys_input"],
        "Literal Eval": [],
        "Combine": [],
        "Append or Update": ["append_update_data"],
        "Remove Keys": ["remove_keys_input"],
        "Rename Keys": ["rename_keys_input"],
        "Path Selection": ["mapped_json_display", "selected_key"],
        "JQ Expression": ["query"],
        # Table
        "Add Column": ["new_column_name", "new_column_value"],
        "Concatenate": [],
        "Drop Column": ["column_name"],
        "Filter": ["column_name", "filter_value", "filter_operator"],
        "Head": ["num_rows"],
        "Merge": ["left_dataframe", "right_dataframe", "merge_on_column", "merge_how"],
        "Rename Column": ["column_name", "new_column_name"],
        "Replace Value": ["column_name", "replace_value", "replacement_value"],
        "Select Columns": ["columns_to_select"],
        "Sort": ["column_name", "ascending"],
        "Tail": ["num_rows"],
        "Drop Duplicates": ["column_name"],
        # Text
        "Word Count": ["count_words", "count_characters", "count_lines"],
        "Case Conversion": ["case_type"],
        "Text Replace": ["search_pattern", "replacement_text", "use_regex"],
        "Text Extract": ["extract_pattern", "max_matches"],
        "Text Head": ["head_characters"],
        "Text Tail": ["tail_characters"],
        "Text Strip": ["strip_mode", "strip_characters"],
        "Text Join": ["text_input_2"],
        "Text Clean": ["remove_extra_spaces", "remove_special_chars", "remove_empty_lines"],
        "Text to DataFrame": ["table_separator", "has_header"],
    }

    # The three main inputs (one per data type). They are never treated as
    # operation-specific fields; the input-type selector toggles them.
    MAIN_INPUTS = ("text_input", "data", "df")

    # Every operation-specific field (union of all the lists above), used to
    # hide and reset fields whenever the input type or operation changes.
    ALL_OPERATION_FIELDS: list[str] = [
        # JSON
        "select_keys_input",
        "append_update_data",
        "remove_keys_input",
        "rename_keys_input",
        "mapped_json_display",
        "selected_key",
        "query",
        # Table
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
        "left_dataframe",
        "right_dataframe",
        "merge_on_column",
        "merge_how",
        # Text
        "table_separator",
        "has_header",
        "count_words",
        "count_characters",
        "count_lines",
        "case_type",
        "use_regex",
        "search_pattern",
        "replacement_text",
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
    ]

    # Defaults applied to the JSON operation fields when the operation changes,
    # mirroring the JSON Operations component's reset behavior.
    OPERATION_FIELD_DEFAULTS: dict[str, Any] = {
        "select_keys_input": [],
        "append_update_data": {"key": "value"},
        "remove_keys_input": [],
        "rename_keys_input": {"old_key": "new_key"},
        "mapped_json_display": "",
        "selected_key": None,
        "query": "",
    }

    inputs = [
        # --- Input type selector: drives operations, input, and output ---
        TabInput(
            name="input_type",
            display_name="Input Type",
            options=INPUT_TYPES,
            value="Text",
            info="Select the type of input to operate on.",
            real_time_refresh=True,
        ),
        # --- Main inputs: one per data type, shown contextually ---
        MultilineInput(
            name="text_input",
            display_name="Text",
            info="The input text to process.",
            show=True,
        ),
        DataInput(
            name="data",
            display_name="JSON",
            info="The JSON / Data object to operate on.",
            is_list=True,
            show=False,
        ),
        DataFrameInput(
            name="df",
            display_name="Table",
            info="The input Table to operate on. Connect multiple Tables for merge or concatenate operations.",
            is_list=True,
            show=False,
        ),
        # --- Operation picker (options are filtered by Input Type) ---
        SortableListInput(
            name="operation",
            display_name="Operation",
            placeholder="Select Operation",
            info="Select the operation to perform. The matching fields and output appear once you choose one.",
            options=OPERATIONS_BY_TYPE["Text"],
            real_time_refresh=True,
            limit=1,
        ),
        # --- JSON operation fields ---
        MessageTextInput(
            name="select_keys_input",
            display_name="Select Keys",
            info="List of keys to select from the data. Only top-level keys can be selected.",
            show=False,
            is_list=True,
            value=[],
        ),
        DictInput(
            name="append_update_data",
            display_name="Append or Update",
            info="Data to append or update the existing data with. Only top-level keys are checked.",
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
            value=[],
        ),
        DictInput(
            name="rename_keys_input",
            display_name="Rename Keys",
            info="List of keys to rename in the data.",
            show=False,
            is_list=True,
            value={"old_key": "new_key"},
        ),
        MultilineInput(
            name="mapped_json_display",
            display_name="JSON to Map",
            info="Paste or preview your JSON here to explore its structure and select a path for extraction.",
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
            value=None,
        ),
        MessageTextInput(
            name="query",
            display_name="JQ Expression",
            info="JSON Query to filter the data. Used by Path Selection and JQ Expression operations.",
            placeholder="e.g., .properties.id",
            show=False,
        ),
        # --- Table operation fields ---
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
            advanced=False,
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
            info="Number of rows to return (for head/tail).",
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
        DataFrameInput(
            name="left_dataframe",
            display_name="Left Table",
            info="The left (primary) Table for merge operations. "
            "In a left merge, all rows from this table are preserved.",
            dynamic=True,
            show=False,
        ),
        DataFrameInput(
            name="right_dataframe",
            display_name="Right Table",
            info="The right (secondary) Table for merge operations. "
            "In a right merge, all rows from this table are preserved.",
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="merge_on_column",
            display_name="Merge On Column",
            info="The column name to merge Tables on. Must exist in both Tables.",
            dynamic=True,
            show=False,
        ),
        DropdownInput(
            name="merge_how",
            display_name="Merge Type",
            options=["inner", "outer", "left", "right"],
            value="inner",
            info="Type of merge: inner (intersection), outer (union), left, or right.",
            dynamic=True,
            show=False,
        ),
        # --- Text operation fields ---
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
            info="Number of characters to extract from the beginning of text. Must be non-negative.",
            value=100,
            dynamic=True,
            show=False,
            range_spec=RangeSpec(min=0, max=1000000, step=1, step_type="int"),
        ),
        IntInput(
            name="tail_characters",
            display_name="Characters from End",
            info="Number of characters to extract from the end of text. Must be non-negative.",
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
        MultilineInput(
            name="text_input_2",
            display_name="Second Text Input",
            info="Second text to join with the first text.",
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
    ]

    # Default output matches the default Input Type ("Text" -> Message).
    # update_outputs / update_frontend_node narrow it to the selected type and
    # operation.
    outputs = [Output(display_name="Message", name="message_output", method="as_message")]

    # ------------------------------------------------------------------
    # Operation routing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_operation_name(field_value: Any) -> str:
        """Extract the operation name from a SortableListInput value."""
        if isinstance(field_value, list) and len(field_value) > 0 and isinstance(field_value[0], dict):
            return field_value[0].get("name", "")
        if isinstance(field_value, str):
            return field_value
        return ""

    def _operation_name(self) -> str:
        """Get the currently selected operation name."""
        return self._extract_operation_name(getattr(self, "operation", []))

    @staticmethod
    def _default_output_for_type(input_type: str) -> Output:
        """Return the output advertised for an input type when no operation is selected yet."""
        if input_type == "JSON":
            return Output(display_name="JSON", name="data_output", method="as_data")
        if input_type == "Table":
            return Output(display_name="Table", name="dataframe_output", method="as_dataframe")
        return Output(display_name="Message", name="message_output", method="as_message")

    # ------------------------------------------------------------------
    # Dynamic UI
    # ------------------------------------------------------------------
    def _reset_operation_fields(self, build_config: dotdict) -> None:
        """Hide every operation-specific field and restore its default value."""
        for field in self.ALL_OPERATION_FIELDS:
            if field in build_config:
                build_config[field]["show"] = False
                if field in self.OPERATION_FIELD_DEFAULTS:
                    build_config[field]["value"] = self.OPERATION_FIELD_DEFAULTS[field]

    def _show_main_input(self, build_config: dotdict, input_type: str, operation: str) -> None:
        """Show only the main input that matches the input type; hide the others."""
        for inp in self.MAIN_INPUTS:
            if inp in build_config:
                build_config[inp]["show"] = False
                build_config[inp]["required"] = False

        main_input = INPUT_TYPE_TO_MAIN_INPUT.get(input_type)
        if main_input and main_input in build_config:
            build_config[main_input]["show"] = True
            build_config[main_input]["required"] = True
            # The JSON "Combine" operation consumes a list of Data objects.
            if main_input == "data":
                build_config["data"]["is_list"] = operation == "Combine"

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        # Path Selection: refresh the available JSON paths from the pasted JSON.
        if field_name == "mapped_json_display":
            try:
                parsed_json = json.loads(field_value)
                keys = self.extract_all_paths(parsed_json)
                build_config["selected_key"]["options"] = keys
                build_config["selected_key"]["show"] = True
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.error(f"Error parsing mapped JSON: {e}")
                build_config["selected_key"]["show"] = False
            return build_config

        # Input type changed: swap the operation list, clear the selection, and
        # show only the matching input. No operation-specific fields are shown
        # until an operation is picked.
        if field_name == "input_type":
            input_type = field_value if field_value in OPERATIONS_BY_TYPE else "Text"
            build_config["operation"]["options"] = OPERATIONS_BY_TYPE[input_type]
            build_config["operation"]["value"] = []
            self._reset_operation_fields(build_config)
            self._show_main_input(build_config, input_type, operation="")
            return build_config

        # Operation changed: reset fields, show the input for the current type,
        # then reveal the operation-specific fields.
        if field_name == "operation":
            operation = self._extract_operation_name(field_value)
            self._reset_operation_fields(build_config)

            input_type = build_config.get("input_type", {}).get("value", "Text")
            self._show_main_input(build_config, input_type, operation)

            for field in self.OPERATION_FIELDS.get(operation, []):
                if field in build_config:
                    build_config[field]["show"] = True

            return build_config

        return build_config

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Create the output(s) appropriate to the selected input type and operation."""
        if field_name == "input_type":
            # Switching type clears the operation; advertise the type's default.
            input_type = field_value if field_value in OPERATIONS_BY_TYPE else "Text"
            frontend_node["outputs"] = [self._default_output_for_type(input_type)]
            return frontend_node

        template = frontend_node.get("template", {})
        input_type = template.get("input_type", {}).get("value", "Text")

        if field_name == "operation":
            operation = self._extract_operation_name(field_value)
        else:
            # Any other refresh (e.g. Path Selection's "JSON to Map" field)
            # reaches here on a freshly rebuilt node whose outputs were reset
            # to the class default (Message). Re-derive the output from the
            # saved operation so the refresh doesn't swap the real output type.
            operation = self._extract_operation_name(template.get("operation", {}).get("value", []))

        if not operation:
            # No operation selected: fall back to the input type's default output.
            frontend_node["outputs"] = [self._default_output_for_type(input_type)]
            return frontend_node

        frontend_node["outputs"] = []
        if operation in JSON_OPERATIONS or operation == "Word Count":
            frontend_node["outputs"].append(Output(display_name="JSON", name="data_output", method="as_data"))
        elif operation in TABLE_OPERATIONS or operation == "Text to DataFrame":
            frontend_node["outputs"].append(
                Output(display_name="Table", name="dataframe_output", method="as_dataframe")
            )
        elif operation == "Text Join":
            frontend_node["outputs"].append(Output(display_name="Text", name="text_output", method="as_text"))
            frontend_node["outputs"].append(Output(display_name="Message", name="message_output", method="as_message"))
        else:
            frontend_node["outputs"].append(Output(display_name="Message", name="message_output", method="as_message"))

        return frontend_node

    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict) -> dict:
        """Keep the operation options and outputs in sync with the saved input type on load."""
        await super().update_frontend_node(new_frontend_node, current_frontend_node)

        template = new_frontend_node.get("template", {})
        input_type = template.get("input_type", {}).get("value", "Text")
        if input_type not in OPERATIONS_BY_TYPE:
            input_type = "Text"

        # Filter the operation picker to the saved input type.
        if "operation" in template:
            template["operation"]["options"] = OPERATIONS_BY_TYPE[input_type]

        # Re-derive the outputs from the saved input type + operation.
        operation_value = template.get("operation", {}).get("value", [])
        if self._extract_operation_name(operation_value):
            self.update_outputs(new_frontend_node, "operation", operation_value)
        else:
            self.update_outputs(new_frontend_node, "input_type", input_type)

        return new_frontend_node

    # ==================================================================
    # Output methods (referenced by update_outputs)
    # ==================================================================
    def as_data(self) -> Data:
        """JSON-typed output: JSON operations and Word Count."""
        operation = self._operation_name()
        if operation in JSON_OPERATIONS:
            handler = self._json_handlers().get(operation)
            if handler:
                try:
                    return handler()
                except Exception as e:
                    logger.error(f"Error executing {operation}: {e!s}")
                    raise
        if operation == "Word Count":
            return self._word_count_data()
        return Data(data={})

    def as_dataframe(self) -> DataFrame:
        """Table-typed output: Table operations and Text to DataFrame."""
        operation = self._operation_name()
        if operation in TABLE_OPERATIONS:
            return self._run_table_operation(operation)
        if operation == "Text to DataFrame":
            return self._text_to_dataframe(getattr(self, "text_input", "") or "")
        return DataFrame(pd.DataFrame())

    def as_message(self) -> Message:
        """Message-typed output: generic text operations (and Text Join)."""
        return Message(text=self._format_result_as_text(self._run_text_operation()))

    def as_text(self) -> Message:
        """Text output for the Text Join operation."""
        return self.as_message()

    # ==================================================================
    # JSON operations
    # ==================================================================
    @staticmethod
    def extract_all_paths(obj, path=""):
        paths = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_path = f"{path}.{k}" if path else f".{k}"
                paths.append(new_path)
                paths.extend(OperationsComponent.extract_all_paths(v, new_path))
        elif isinstance(obj, list) and obj:
            new_path = f"{path}[0]"
            paths.append(new_path)
            paths.extend(OperationsComponent.extract_all_paths(obj[0], new_path))
        return paths

    @staticmethod
    def remove_keys_recursive(obj, keys_to_remove):
        if isinstance(obj, dict):
            return {
                k: OperationsComponent.remove_keys_recursive(v, keys_to_remove)
                for k, v in obj.items()
                if k not in keys_to_remove
            }
        if isinstance(obj, list):
            return [OperationsComponent.remove_keys_recursive(item, keys_to_remove) for item in obj]
        return obj

    @staticmethod
    def rename_keys_recursive(obj, rename_map):
        if isinstance(obj, dict):
            return {
                rename_map.get(k, k): OperationsComponent.rename_keys_recursive(v, rename_map) for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [OperationsComponent.rename_keys_recursive(item, rename_map) for item in obj]
        return obj

    def _json_handlers(self) -> "dict[str, Callable[[], Data]]":
        return {
            "Select Keys": self.select_keys,
            "Literal Eval": self.evaluate_data,
            "Combine": self.combine_data,
            "Append or Update": self.append_update,
            "Remove Keys": self.remove_keys,
            "Rename Keys": self.rename_keys,
            "Path Selection": self.json_path,
            "JQ Expression": self.json_query,
        }

    def get_data_dict(self) -> dict:
        """Extract data dictionary from Data object."""
        data = self.data[0] if isinstance(self.data, list) and len(self.data) == 1 else self.data
        return data.model_dump()

    def get_normalized_data(self) -> dict:
        """Get normalized data dictionary, handling the 'data' key if present."""
        data_dict = self.get_data_dict()
        return data_dict.get("data", data_dict)

    def data_is_list(self) -> bool:
        """Check if data contains multiple items."""
        return isinstance(self.data, list) and len(self.data) > 1

    def validate_single_data(self, operation: str) -> None:
        """Validate that the operation is being performed on a single data object."""
        if self.data_is_list():
            msg = f"{operation} operation is not supported for multiple data objects."
            raise ValueError(msg)

    def select_keys(self) -> Data:
        """Select specific keys from the data dictionary."""
        self.validate_single_data("Select Keys")
        data_dict = self.get_normalized_data()
        filter_criteria: list[str] = self.select_keys_input

        if len(filter_criteria) == 1 and filter_criteria[0] == "data":
            filtered = data_dict["data"]
        else:
            if not all(key in data_dict for key in filter_criteria):
                msg = f"Select key not found in data. Available keys: {list(data_dict.keys())}"
                raise ValueError(msg)
            filtered = {key: value for key, value in data_dict.items() if key in filter_criteria}

        return Data(data=filtered)

    def remove_keys(self) -> Data:
        """Remove specified keys from the data dictionary, recursively."""
        self.validate_single_data("Remove Keys")
        data_dict = self.get_normalized_data()
        remove_keys_input: list[str] = self.remove_keys_input
        filtered = OperationsComponent.remove_keys_recursive(data_dict, set(remove_keys_input))
        return Data(data=filtered)

    def rename_keys(self) -> Data:
        """Rename keys in the data dictionary, recursively."""
        self.validate_single_data("Rename Keys")
        data_dict = self.get_normalized_data()
        rename_keys_input: dict[str, str] = self.rename_keys_input
        renamed = OperationsComponent.rename_keys_recursive(data_dict, rename_keys_input)
        return Data(data=renamed)

    def recursive_eval(self, data: Any) -> Any:
        """Recursively evaluate string values that look like Python literals."""
        if isinstance(data, dict):
            return {k: self.recursive_eval(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.recursive_eval(item) for item in data]
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

    def evaluate_data(self) -> Data:
        """Evaluate string values in the data dictionary."""
        self.validate_single_data("Literal Eval")
        logger.info("evaluating data")
        return Data(**self.recursive_eval(self.get_data_dict()))

    def combine_data(self) -> Data:
        """Combine multiple data objects into one."""
        logger.info("combining data")
        if not self.data_is_list():
            return self.data[0] if self.data else Data(data={})

        data_dicts = [data.model_dump().get("data", data.model_dump()) for data in self.data]
        combined_data: dict[str, Any] = {}

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

    def append_update(self) -> Data:
        """Append or update the data with new key-value pairs."""
        self.validate_single_data("Append or Update")
        data_filtered = self.get_normalized_data()
        for key, value in self.append_update_data.items():
            data_filtered[key] = value
        return Data(**data_filtered)

    def json_path(self) -> Data:
        """Extract a value from the data using the selected JQ path."""
        try:
            import jq
        except ImportError:
            msg = "jq is required for Path Selection. Install with: pip install jq"
            raise ImportError(msg) from None

        try:
            if not self.data or not self.selected_key:
                msg = "Missing input data or selected key."
                raise ValueError(msg)
            input_payload = self.data[0].data if isinstance(self.data, list) else self.data.data
            compiled = jq.compile(self.selected_key)
            result = compiled.input(input_payload).first()
            if isinstance(result, dict):
                return Data(data=result)
            return Data(data={"result": result})
        except (ValueError, TypeError, KeyError) as e:
            self.status = f"Error: {e!s}"
            self.log(self.status)
            return Data(data={"error": str(e)})

    def json_query(self) -> Data:
        """Run a JQ expression against the data."""
        try:
            import jq
        except ImportError:
            msg = "jq is required for JQ Expression. Install with: pip install jq"
            raise ImportError(msg) from None

        if not self.query or not self.query.strip():
            msg = "JSON Query is required and cannot be blank."
            raise ValueError(msg)
        raw_data = self.get_data_dict()
        try:
            input_str = json.dumps(raw_data)
            repaired = repair_json(input_str)
            data_json = json.loads(repaired)
            jq_input = data_json["data"] if isinstance(data_json, dict) and "data" in data_json else data_json
            results = jq.compile(self.query).input(jq_input).all()
            if not results:
                msg = "No result from JSON query."
                raise ValueError(msg)
            result = results[0] if len(results) == 1 else results
            if result is None or result == "None":
                msg = "JSON query returned null/None. Check if the path exists in your data."
                raise ValueError(msg)
            if isinstance(result, dict):
                return Data(data=result)
            return Data(data={"result": result})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            logger.error(f"JSON Query failed: {e}")
            msg = f"JSON Query error: {e}"
            raise ValueError(msg) from e

    # ==================================================================
    # Table operations
    # ==================================================================
    def _get_primary_dataframe(self) -> DataFrame:
        """Get the first DataFrame from input (handles both single and list inputs)."""
        if isinstance(self.df, list):
            return self.df[0].copy() if self.df else DataFrame()
        return self.df.copy()

    def _run_table_operation(self, operation: str) -> DataFrame:
        # Merge and Concatenate use their own inputs, not the primary df.
        if operation == "Merge":
            return self.merge_dataframes()
        if operation == "Concatenate":
            return self.concatenate_dataframes()

        df_copy = self._get_primary_dataframe()
        table_handlers = {
            "Filter": self.filter_rows_by_value,
            "Sort": self.sort_by_column,
            "Drop Column": self.drop_column,
            "Rename Column": self.rename_column,
            "Add Column": self.add_column,
            "Select Columns": self.select_columns,
            "Head": self.head,
            "Tail": self.tail,
            "Replace Value": self.replace_values,
            "Drop Duplicates": self.drop_duplicates,
        }
        handler = table_handlers.get(operation)
        if handler is None:
            msg = f"Unsupported operation: {operation}"
            logger.error(msg)
            raise ValueError(msg)
        return handler(df_copy)

    def filter_rows_by_value(self, df: DataFrame) -> DataFrame:
        column = df[self.column_name]
        filter_value = self.filter_value
        operator = getattr(self, "filter_operator", "equals")

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

    def sort_by_column(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.sort_values(by=self.column_name, ascending=self.ascending))

    def drop_column(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.drop(columns=[self.column_name]))

    def rename_column(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.rename(columns={self.column_name: self.new_column_name}))

    def add_column(self, df: DataFrame) -> DataFrame:
        df[self.new_column_name] = [self.new_column_value] * len(df)
        return DataFrame(df)

    def select_columns(self, df: DataFrame) -> DataFrame:
        columns = [col.strip() for col in self.columns_to_select]
        return DataFrame(df[columns])

    def head(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.head(self.num_rows))

    def tail(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.tail(self.num_rows))

    def replace_values(self, df: DataFrame) -> DataFrame:
        df[self.column_name] = df[self.column_name].replace(self.replace_value, self.replacement_value)
        return DataFrame(df)

    def drop_duplicates(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.drop_duplicates(subset=self.column_name))

    def concatenate_dataframes(self) -> DataFrame:
        """Concatenate multiple DataFrames vertically (stack rows)."""
        if not isinstance(self.df, list) or len(self.df) == 0:
            return self.df.copy() if self.df is not None else DataFrame()

        if len(self.df) == 1:
            return self.df[0].copy()

        concatenated = pd.concat(self.df, ignore_index=True)
        return DataFrame(concatenated)

    def merge_dataframes(self) -> DataFrame:
        """Merge two DataFrames based on a common column (join operation)."""
        left_df = getattr(self, "left_dataframe", None)
        right_df = getattr(self, "right_dataframe", None)

        if left_df is None:
            return DataFrame()
        if right_df is None:
            return left_df.copy()

        df_left = left_df.copy()
        df_right = right_df.copy()

        merge_on = getattr(self, "merge_on_column", None)
        merge_how = getattr(self, "merge_how", "inner")

        if merge_on:
            if merge_on not in df_left.columns:
                msg = f"Column '{merge_on}' not found in left DataFrame. Available: {list(df_left.columns)}"
                raise ValueError(msg)
            if merge_on not in df_right.columns:
                msg = f"Column '{merge_on}' not found in right DataFrame. Available: {list(df_right.columns)}"
                raise ValueError(msg)
            merged = df_left.merge(df_right, on=merge_on, how=merge_how, suffixes=("", "_right"))
        else:
            merged = df_left.merge(df_right, left_index=True, right_index=True, how=merge_how, suffixes=("", "_right"))

        cols_to_drop = []
        for col in merged.columns:
            if col.endswith("_right"):
                original_col = col[:-6]
                if original_col in merged.columns:
                    merged[original_col] = merged[original_col].combine_first(merged[col])
                    cols_to_drop.append(col)

        if cols_to_drop:
            merged = merged.drop(columns=cols_to_drop)

        return DataFrame(merged)

    # ==================================================================
    # Text operations
    # ==================================================================
    def _run_text_operation(self) -> Any:
        """Process text based on the selected operation (Message/Text outputs)."""
        text = getattr(self, "text_input", "")
        operation = self._operation_name()

        # Allow empty text for Text Join (second input may have content).
        if not text and operation != "Text Join":
            return None

        text_handlers = {
            "Case Conversion": self._case_conversion,
            "Text Replace": self._text_replace,
            "Text Extract": self._text_extract,
            "Text Head": self._text_head,
            "Text Tail": self._text_tail,
            "Text Strip": self._text_strip,
            "Text Join": self._text_join,
            "Text Clean": self._text_clean,
        }
        handler = text_handlers.get(operation)
        if handler:
            return handler(text)
        return text

    def _word_count_data(self) -> Data:
        """Word Count operation result as a Data object."""
        result = self._word_count(getattr(self, "text_input", "") or "")
        return Data(data=result)

    def _word_count(self, text: str) -> dict[str, Any]:
        """Count words, characters, and lines in text."""
        result: dict[str, Any] = {}
        text_str = str(text) if text else ""
        is_empty = not text_str or not text_str.strip()

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

    def _text_to_dataframe(self, text: str) -> DataFrame:
        """Convert markdown-style table text to a DataFrame."""
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        if not lines:
            return DataFrame(pd.DataFrame())

        separator = getattr(self, "table_separator", "|")
        has_header = getattr(self, "has_header", True)

        rows = self._parse_table_rows(lines, separator)
        if not rows:
            return DataFrame(pd.DataFrame())

        df = self._create_dataframe(rows, has_header=has_header)
        self._convert_numeric_columns(df)
        self.log(f"Converted text to DataFrame: {len(df)} rows, {len(df.columns)} columns")
        return DataFrame(df)

    def _parse_table_rows(self, lines: list[str], separator: str) -> list[list[str]]:
        rows = []
        for line in lines:
            cleaned_line = line.strip(separator)
            cells = [cell.strip() for cell in cleaned_line.split(separator)]
            rows.append(cells)
        return rows

    def _create_dataframe(self, rows: list[list[str]], *, has_header: bool) -> pd.DataFrame:
        if has_header and len(rows) > 1:
            header = rows[0]
            data_rows = rows[1:]
            header_col_count = len(header)
            for i, row in enumerate(data_rows):
                row_col_count = len(row)
                if row_col_count != header_col_count:
                    msg = (
                        f"Header mismatch: {header_col_count} column(s) in header vs "
                        f"{row_col_count} column(s) in data row {i + 1}. "
                        "Please ensure the header has the same number of columns as your data."
                    )
                    raise ValueError(msg)
            return pd.DataFrame(data_rows, columns=header)

        max_cols = max(len(row) for row in rows) if rows else 0
        columns = [f"col_{i}" for i in range(max_cols)]
        return pd.DataFrame(rows, columns=columns)

    def _convert_numeric_columns(self, df: pd.DataFrame) -> None:
        for col in df.columns:
            with contextlib.suppress(ValueError, TypeError):
                df[col] = pd.to_numeric(df[col])

    def _case_conversion(self, text: str) -> str:
        case_type = getattr(self, "case_type", "lowercase")
        converter = CASE_CONVERTERS.get(case_type)
        return converter(text) if converter else text

    def _text_replace(self, text: str) -> str:
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

    def _text_extract(self, text: str) -> list[str]:
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

    def _text_head(self, text: str) -> str:
        head_characters = getattr(self, "head_characters", 100)
        if head_characters < 0:
            msg = f"Characters from Start must be a non-negative integer, got {head_characters}"
            raise ValueError(msg)
        if head_characters == 0:
            return ""
        return text[:head_characters]

    def _text_tail(self, text: str) -> str:
        tail_characters = getattr(self, "tail_characters", 100)
        if tail_characters < 0:
            msg = f"Characters from End must be a non-negative integer, got {tail_characters}"
            raise ValueError(msg)
        if tail_characters == 0:
            return ""
        return text[-tail_characters:]

    def _text_strip(self, text: str) -> str:
        strip_mode = getattr(self, "strip_mode", "both")
        strip_characters = getattr(self, "strip_characters", "")
        text_str = str(text) if text else ""
        chars_to_strip = strip_characters if strip_characters else None
        if strip_mode == "left":
            return text_str.lstrip(chars_to_strip)
        if strip_mode == "right":
            return text_str.rstrip(chars_to_strip)
        return text_str.strip(chars_to_strip)

    def _text_join(self, text: str) -> str:
        text_input_2 = getattr(self, "text_input_2", "")
        text1 = str(text) if text else ""
        text2 = str(text_input_2) if text_input_2 else ""
        if text1 and text2:
            return f"{text1}\n{text2}"
        return text1 or text2

    def _text_clean(self, text: str) -> str:
        result = text
        if getattr(self, "remove_extra_spaces", True):
            # Collapse runs of horizontal whitespace but preserve newlines so
            # that remove_empty_lines stays effective when both are enabled.
            result = re.sub(r"[^\S\n]+", " ", result)
        if getattr(self, "remove_special_chars", False):
            result = re.sub(r"[^\w\s]", "", result)
        if getattr(self, "remove_empty_lines", False):
            lines = [line for line in result.split("\n") if line.strip()]
            result = "\n".join(lines)
        return result

    def _format_result_as_text(self, result: Any) -> str:
        if result is None:
            return ""
        if isinstance(result, list):
            return "\n".join(str(item) for item in result)
        return str(result)

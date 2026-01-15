import contextlib
import re
from typing import Any

import pandas as pd

from lfx.custom import Component
from lfx.field_typing import RangeSpec
from lfx.inputs import (
    BoolInput,
    DropdownInput,
    IntInput,
    SortableListInput,
    StrInput,
)
from lfx.inputs.inputs import MultilineInput
from lfx.io import Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


class TextOperations(Component):
    display_name = "Text Operations"
    description = "Perform various text processing operations including text-to-DataFrame conversion."
    icon = "type"
    name = "TextOperations"

    # Configuration for operation-specific input fields
    OPERATION_FIELDS: dict[str, list[str]] = {
        "Text to DataFrame": ["table_separator", "has_header"],
        "Word Count": ["count_words", "count_characters", "count_lines"],
        "Case Conversion": ["case_type"],
        "Text Replace": ["search_pattern", "replacement_text", "use_regex"],
        "Text Extract": ["extract_pattern", "max_matches"],
        "Text Head": ["head_characters"],
        "Text Tail": ["tail_characters"],
        "Text Strip": ["strip_mode", "strip_characters"],
        "Text Join": ["text_input_2"],
        "Text Clean": ["remove_extra_spaces", "remove_special_chars", "remove_empty_lines"],
    }

    ALL_DYNAMIC_FIELDS: list[str] = [
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
    ]

    CASE_CONVERTERS: dict[str, Any] = {
        "uppercase": str.upper,
        "lowercase": str.lower,
        "title": str.title,
        "capitalize": str.capitalize,
        "swapcase": str.swapcase,
    }

    inputs = [
        MultilineInput(
            name="text_input",
            display_name="Text Input",
            info="The input text to process.",
            required=True,
        ),
        SortableListInput(
            name="operation",
            display_name="Operation",
            placeholder="Select Operation",
            info="Select the text operation to perform.",
            options=[
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
            real_time_refresh=True,
            limit=1,
        ),
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

    outputs = []

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update build configuration to show/hide relevant inputs based on operation."""
        for field in self.ALL_DYNAMIC_FIELDS:
            if field in build_config:
                build_config[field]["show"] = False

        if field_name != "operation":
            return build_config

        operation_name = self._extract_operation_name(field_value)
        if not operation_name:
            return build_config

        fields_to_show = self.OPERATION_FIELDS.get(operation_name, [])
        for field in fields_to_show:
            if field in build_config:
                build_config[field]["show"] = True

        return build_config

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Create dynamic outputs based on selected operation."""
        if field_name != "operation":
            return frontend_node

        frontend_node["outputs"] = []
        operation_name = self._extract_operation_name(field_value)

        if operation_name == "Word Count":
            frontend_node["outputs"].append(Output(display_name="Data", name="data", method="get_data"))
        elif operation_name == "Text to DataFrame":
            frontend_node["outputs"].append(Output(display_name="DataFrame", name="dataframe", method="get_dataframe"))
        elif operation_name == "Text Join":
            frontend_node["outputs"].append(Output(display_name="Text", name="text", method="get_text"))
            frontend_node["outputs"].append(Output(display_name="Message", name="message", method="get_message"))
        elif operation_name:
            frontend_node["outputs"].append(Output(display_name="Message", name="message", method="get_message"))

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

    def process_text(self) -> Any:
        """Process text based on selected operation."""
        text = getattr(self, "text_input", "")
        operation = self.get_operation_name()

        # Allow empty text for Text Join (second input might have content)
        # and Word Count (should return zeros for empty text)
        if not text and operation not in ("Text Join", "Word Count"):
            return None
        operation_handlers = {
            "Text to DataFrame": self._text_to_dataframe,
            "Word Count": self._word_count,
            "Case Conversion": self._case_conversion,
            "Text Replace": self._text_replace,
            "Text Extract": self._text_extract,
            "Text Head": self._text_head,
            "Text Tail": self._text_tail,
            "Text Strip": self._text_strip,
            "Text Join": self._text_join,
            "Text Clean": self._text_clean,
        }

        handler = operation_handlers.get(operation)
        if handler:
            return handler(text)
        return text

    def _text_to_dataframe(self, text: str) -> DataFrame:
        """Convert markdown-style table text to DataFrame."""
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
        """Parse table lines into rows of cells."""
        rows = []
        for line in lines:
            cleaned_line = line.strip(separator)
            cells = [cell.strip() for cell in cleaned_line.split(separator)]
            rows.append(cells)
        return rows

    def _create_dataframe(self, rows: list[list[str]], *, has_header: bool) -> pd.DataFrame:
        """Create DataFrame from parsed rows."""
        if has_header and len(rows) > 1:
            header = rows[0]
            data_rows = rows[1:]
            header_col_count = len(header)

            # Validate that all data rows have the same number of columns as header
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
        """Attempt to convert string columns to numeric where possible."""
        for col in df.columns:
            with contextlib.suppress(ValueError, TypeError):
                df[col] = pd.to_numeric(df[col])

    def _word_count(self, text: str) -> dict[str, Any]:
        """Count words, characters, and lines in text."""
        result: dict[str, Any] = {}

        # Handle empty or whitespace-only text - return zeros
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

    def _case_conversion(self, text: str) -> str:
        """Convert text case."""
        case_type = getattr(self, "case_type", "lowercase")
        converter = self.CASE_CONVERTERS.get(case_type)
        return converter(text) if converter else text

    def _text_replace(self, text: str) -> str:
        """Replace text patterns."""
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
        """Extract text matching patterns."""
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
        """Extract characters from the beginning of text."""
        head_characters = getattr(self, "head_characters", 100)
        if head_characters < 0:
            msg = f"Characters from Start must be a non-negative integer, got {head_characters}"
            raise ValueError(msg)
        if head_characters == 0:
            return ""
        return text[:head_characters]

    def _text_tail(self, text: str) -> str:
        """Extract characters from the end of text."""
        tail_characters = getattr(self, "tail_characters", 100)
        if tail_characters < 0:
            msg = f"Characters from End must be a non-negative integer, got {tail_characters}"
            raise ValueError(msg)
        if tail_characters == 0:
            return ""
        return text[-tail_characters:]

    def _text_strip(self, text: str) -> str:
        """Remove whitespace or specific characters from text edges."""
        strip_mode = getattr(self, "strip_mode", "both")
        strip_characters = getattr(self, "strip_characters", "")

        # Convert to string to ensure proper handling
        text_str = str(text) if text else ""

        # None means strip all whitespace (spaces, tabs, newlines, etc.)
        chars_to_strip = strip_characters if strip_characters else None

        if strip_mode == "left":
            return text_str.lstrip(chars_to_strip)
        if strip_mode == "right":
            return text_str.rstrip(chars_to_strip)
        # Default: "both"
        return text_str.strip(chars_to_strip)

    def _text_join(self, text: str) -> str:
        """Join two texts with line break separator."""
        text_input_2 = getattr(self, "text_input_2", "")

        text1 = str(text) if text else ""
        text2 = str(text_input_2) if text_input_2 else ""

        if text1 and text2:
            return f"{text1}\n{text2}"
        return text1 or text2

    def _text_clean(self, text: str) -> str:
        """Clean text by removing extra spaces, special chars, etc."""
        result = text

        if getattr(self, "remove_extra_spaces", True):
            result = re.sub(r"\s+", " ", result)

        if getattr(self, "remove_special_chars", False):
            # Remove ALL special characters except alphanumeric and spaces
            result = re.sub(r"[^\w\s]", "", result)

        if getattr(self, "remove_empty_lines", False):
            lines = [line for line in result.split("\n") if line.strip()]
            result = "\n".join(lines)

        return result

    def _format_result_as_text(self, result: Any) -> str:
        """Format result as text string."""
        if result is None:
            return ""
        if isinstance(result, list):
            return "\n".join(str(item) for item in result)
        return str(result)

    def get_dataframe(self) -> DataFrame:
        """Return result as DataFrame - only for Text to DataFrame operation."""
        if self.get_operation_name() != "Text to DataFrame":
            return DataFrame(pd.DataFrame())

        text = getattr(self, "text_input", "")
        if not text:
            return DataFrame(pd.DataFrame())

        return self._text_to_dataframe(text)

    def get_text(self) -> Message:
        """Return result as Message - for text operations only."""
        result = self.process_text()
        return Message(text=self._format_result_as_text(result))

    def get_data(self) -> Data:
        """Return result as Data object - only for Word Count operation."""
        if self.get_operation_name() != "Word Count":
            return Data(data={})

        result = self.process_text()
        if result is None:
            return Data(data={})

        if isinstance(result, dict):
            return Data(data=result)
        if isinstance(result, list):
            return Data(data={"items": result})
        return Data(data={"result": str(result)})

    def get_message(self) -> Message:
        """Return result as simple message with the processed text."""
        result = self.process_text()
        return Message(text=self._format_result_as_text(result))

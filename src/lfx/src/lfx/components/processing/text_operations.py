import re
from typing import Any

import pandas as pd

from lfx.custom import Component
from lfx.inputs import (
    BoolInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    SortableListInput,
    StrInput,
)
from lfx.io import Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


class TextOperations(Component):
    display_name = "Text Operations"
    description = "Perform various text processing operations including text-to-DataFrame conversion."
    icon = "type"
    name = "TextOperations"

    OPERATION_CHOICES = [
        "Word Count",
        "Case Conversion",
        "Text Replace",
        "Text Extract",
        "Text Head",
        "Text Tail",
        "Text Strip",
        "Text Join",
        "Text Clean",
        "Text to DataFrame",
    ]

    inputs = [
        MessageTextInput(
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
        # Text to DataFrame specific inputs
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
        # Word Count specific inputs
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
        # Case Conversion specific inputs
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
        # Text Replace specific inputs
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
        # Text Extract specific inputs
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
        # Text Head specific inputs
        IntInput(
            name="head_characters",
            display_name="Characters from Start",
            info="Number of characters to extract from the beginning of text.",
            value=100,
            dynamic=True,
            show=False,
        ),
        # Text Tail specific inputs
        IntInput(
            name="tail_characters",
            display_name="Characters from End",
            info="Number of characters to extract from the end of text.",
            value=100,
            dynamic=True,
            show=False,
        ),
        # Text Strip specific inputs
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
        # Text Join specific inputs
        MessageTextInput(
            name="text_input_2",
            display_name="Second Text Input",
            info="Second text to join with the first text.",
            dynamic=True,
            show=False,
        ),
        # Text Clean specific inputs
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._result = None
        self._operation_result = None

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str = None) -> dict:
        """Update build configuration to show/hide relevant inputs based on operation."""
        # Hide all dynamic inputs by default
        dynamic_fields = [
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

        for field in dynamic_fields:
            if field in build_config:
                build_config[field]["show"] = False

        if field_name == "operation":
            # Handle SortableListInput format
            if isinstance(field_value, list) and len(field_value) > 0:
                operation_name = field_value[0].get("name", "")
            else:
                operation_name = ""

            # Show relevant inputs based on operation
            if operation_name == "Text to DataFrame":
                build_config["table_separator"]["show"] = True
                build_config["has_header"]["show"] = True
            elif operation_name == "Word Count":
                build_config["count_words"]["show"] = True
                build_config["count_characters"]["show"] = True
                build_config["count_lines"]["show"] = True
            elif operation_name == "Case Conversion":
                build_config["case_type"]["show"] = True
            elif operation_name == "Text Replace":
                build_config["search_pattern"]["show"] = True
                build_config["replacement_text"]["show"] = True
                build_config["use_regex"]["show"] = True
            elif operation_name == "Text Extract":
                build_config["extract_pattern"]["show"] = True
                build_config["max_matches"]["show"] = True
            elif operation_name == "Text Head":
                build_config["head_characters"]["show"] = True
            elif operation_name == "Text Tail":
                build_config["tail_characters"]["show"] = True
            elif operation_name == "Text Strip":
                build_config["strip_mode"]["show"] = True
                build_config["strip_characters"]["show"] = True
            elif operation_name == "Text Join":
                build_config["text_input_2"]["show"] = True
            elif operation_name == "Text Clean":
                build_config["remove_extra_spaces"]["show"] = True
                build_config["remove_special_chars"]["show"] = True
                build_config["remove_empty_lines"]["show"] = True

        return build_config

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Create dynamic outputs based on selected operation."""
        if field_name == "operation":
            frontend_node["outputs"] = []

            # Get the selected operation
            if isinstance(field_value, list) and len(field_value) > 0:
                operation_name = field_value[0].get("name", "")
            else:
                operation_name = ""

            # Add outputs based on operation type
            if operation_name == "Word Count":
                frontend_node["outputs"].append(Output(display_name="Data", name="data", method="get_data"))
            elif operation_name == "Text to DataFrame":
                frontend_node["outputs"].append(
                    Output(display_name="DataFrame", name="dataframe", method="get_dataframe")
                )
            elif operation_name == "Text Join":
                frontend_node["outputs"].append(Output(display_name="Text", name="text", method="get_text"))
                frontend_node["outputs"].append(Output(display_name="Message", name="message", method="get_message"))

            # Add Message output for all operations except Word Count, Text to DataFrame, and Text Join
            if operation_name not in ["Word Count", "Text to DataFrame", "Text Join"]:
                frontend_node["outputs"].append(Output(display_name="Message", name="message", method="get_message"))

        return frontend_node

    def get_operation_name(self) -> str:
        """Get the selected operation name."""
        operation_input = getattr(self, "operation", [])
        if isinstance(operation_input, list) and len(operation_input) > 0:
            return operation_input[0].get("name", "")
        return ""

    def process_text(self) -> Any:
        """Process text based on selected operation."""
        text = getattr(self, "text_input", "")
        if not text:
            return None

        operation = self.get_operation_name()

        if operation == "Text to DataFrame":
            return self.text_to_dataframe(text)
        if operation == "Word Count":
            return self.word_count(text)
        if operation == "Case Conversion":
            return self.case_conversion(text)
        if operation == "Text Replace":
            return self.text_replace(text)
        if operation == "Text Extract":
            return self.text_extract(text)
        if operation == "Text Head":
            return self.text_head(text)
        if operation == "Text Tail":
            return self.text_tail(text)
        if operation == "Text Strip":
            return self.text_strip(text)
        if operation == "Text Join":
            return self.text_join(text)
        if operation == "Text Clean":
            return self.text_clean(text)
        return text

    def text_to_dataframe(self, text: str) -> DataFrame:
        """Convert markdown-style table text to DataFrame."""
        try:
            lines = text.strip().split("\n")
            if not lines:
                return DataFrame(pd.DataFrame())

            # Remove empty lines
            lines = [line.strip() for line in lines if line.strip()]

            separator = getattr(self, "table_separator", "|")
            has_header = getattr(self, "has_header", True)

            # Parse table rows
            rows = []
            for line in lines:
                # Remove leading/trailing separators and split
                if line.startswith(separator):
                    line = line[1:]
                if line.endswith(separator):
                    line = line[:-1]

                # Split by separator and clean up
                cells = [cell.strip() for cell in line.split(separator)]
                rows.append(cells)

            if not rows:
                return DataFrame(pd.DataFrame())

            # Create DataFrame
            if has_header and len(rows) > 1:
                # Use first row as header
                df = pd.DataFrame(rows[1:], columns=rows[0])
            else:
                # No header, use generic column names
                max_cols = max(len(row) for row in rows) if rows else 0
                columns = [f"col_{i}" for i in range(max_cols)]
                df = pd.DataFrame(rows, columns=columns)

            # Try to convert numeric columns
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors="ignore")
                except:
                    pass

            self._result = df
            self.log(f"Successfully converted text to DataFrame with {len(df)} rows and {len(df.columns)} columns")
            return DataFrame(df)

        except Exception as e:
            self.log(f"Error converting text to DataFrame: {e!s}")
            return DataFrame(pd.DataFrame({"error": [str(e)]}))

    def word_count(self, text: str) -> dict[str, Any]:
        """Count words, characters, and lines in text."""
        try:
            result = {}

            if getattr(self, "count_words", True):
                words = text.split()
                result["word_count"] = len(words)
                result["unique_words"] = len(set(words))

            if getattr(self, "count_characters", True):
                result["character_count"] = len(text)
                result["character_count_no_spaces"] = len(text.replace(" ", ""))

            if getattr(self, "count_lines", True):
                lines = text.split("\n")
                result["line_count"] = len(lines)
                result["non_empty_lines"] = len([line for line in lines if line.strip()])

            self._result = result
            self.log(f"Text analysis completed: {result}")
            return result

        except Exception as e:
            self.log(f"Error analyzing text: {e!s}")
            return {}

    def case_conversion(self, text: str) -> str:
        """Convert text case."""
        try:
            case_type = getattr(self, "case_type", "lowercase")

            if case_type == "uppercase":
                result = text.upper()
            elif case_type == "lowercase":
                result = text.lower()
            elif case_type == "title":
                result = text.title()
            elif case_type == "capitalize":
                result = text.capitalize()
            elif case_type == "swapcase":
                result = text.swapcase()
            else:
                result = text

            self._result = result
            self.log(f"Text converted to {case_type}")
            return result

        except Exception as e:
            self.log(f"Error converting case: {e!s}")
            return text

    def text_replace(self, text: str) -> str:
        """Replace text patterns."""
        try:
            search_pattern = getattr(self, "search_pattern", "")
            replacement_text = getattr(self, "replacement_text", "")
            use_regex = getattr(self, "use_regex", False)

            if not search_pattern:
                return text

            if use_regex:
                result = re.sub(search_pattern, replacement_text, text)
            else:
                result = text.replace(search_pattern, replacement_text)

            self._result = result
            self.log("Text replacement completed")
            return result

        except Exception as e:
            self.log(f"Error replacing text: {e!s}")
            return text

    def text_extract(self, text: str) -> list[str]:
        """Extract text matching patterns."""
        try:
            extract_pattern = getattr(self, "extract_pattern", "")
            max_matches = getattr(self, "max_matches", 10)

            if not extract_pattern:
                return []

            matches = re.findall(extract_pattern, text)
            if max_matches > 0:
                matches = matches[:max_matches]

            self._result = matches
            self.log(f"Extracted {len(matches)} matches")
            return matches

        except Exception as e:
            self.log(f"Error extracting text: {e!s}")
            return []

    def text_head(self, text: str) -> str:
        """Extract characters from the beginning of text."""
        try:
            head_characters = getattr(self, "head_characters", 100)

            if head_characters <= 0:
                return ""

            result = text[:head_characters]
            self._result = result
            self.log(f"Extracted {len(result)} characters from start")
            return result

        except Exception as e:
            self.log(f"Error extracting head: {e!s}")
            return text

    def text_tail(self, text: str) -> str:
        """Extract characters from the end of text."""
        try:
            tail_characters = getattr(self, "tail_characters", 100)

            if tail_characters <= 0:
                return ""

            result = text[-tail_characters:]
            self._result = result
            self.log(f"Extracted {len(result)} characters from end")
            return result

        except Exception as e:
            self.log(f"Error extracting tail: {e!s}")
            return text

    def text_strip(self, text: str) -> str:
        """Remove whitespace or specific characters from the beginning and/or end of text."""
        try:
            strip_mode = getattr(self, "strip_mode", "both")
            strip_characters = getattr(self, "strip_characters", "")

            if strip_characters:
                # Strip specific characters
                if strip_mode == "both":
                    result = text.strip(strip_characters)
                elif strip_mode == "left":
                    result = text.lstrip(strip_characters)
                elif strip_mode == "right":
                    result = text.rstrip(strip_characters)
                else:
                    result = text.strip(strip_characters)
            # Strip whitespace (default behavior)
            elif strip_mode == "both":
                result = text.strip()
            elif strip_mode == "left":
                result = text.lstrip()
            elif strip_mode == "right":
                result = text.rstrip()
            else:
                result = text.strip()

            self._result = result
            removed_chars = len(text) - len(result)
            self.log(f"Stripped {removed_chars} characters from {strip_mode} side(s)")
            return result

        except Exception as e:
            self.log(f"Error stripping text: {e!s}")
            return text

    def text_split(self, text: str) -> list[str]:
        """Split text by delimiter."""
        try:
            split_delimiter = getattr(self, "split_delimiter", ",")
            max_splits = getattr(self, "max_splits", -1)

            if max_splits > 0:
                result = text.split(split_delimiter, max_splits)
            else:
                result = text.split(split_delimiter)

            # Clean up whitespace
            result = [part.strip() for part in result]

            self._result = result
            self.log(f"Text split into {len(result)} parts")
            return result

        except Exception as e:
            self.log(f"Error splitting text: {e!s}")
            return [text]

    def text_join(self, text: str) -> str:
        """Join two texts with line break separator."""
        try:
            text_input_2 = getattr(self, "text_input_2", "")
            join_separator = "\n"  # Line break as default separator

            # Get both texts
            text1 = str(text) if text else ""
            text2 = str(text_input_2) if text_input_2 else ""

            # Join the two texts with line break
            if text1 and text2:
                result = f"{text1}{join_separator}{text2}"
            elif text1:
                result = text1
            elif text2:
                result = text2
            else:
                result = ""

            self._result = result
            self.log("Texts joined with line break separator")
            return result

        except Exception as e:
            self.log(f"Error joining texts: {e!s}")
            return text

    def text_clean(self, text: str) -> str:
        """Clean text by removing extra spaces, special chars, etc."""
        try:
            result = text

            if getattr(self, "remove_extra_spaces", True):
                # Replace multiple spaces with single space
                result = re.sub(r"\s+", " ", result)

            if getattr(self, "remove_special_chars", False):
                # Keep only alphanumeric, spaces, and basic punctuation
                result = re.sub(r"[^\w\s.,!?;:-]", "", result)

            if getattr(self, "remove_empty_lines", False):
                # Remove empty lines
                lines = result.split("\n")
                lines = [line for line in lines if line.strip()]
                result = "\n".join(lines)

            self._result = result
            self.log("Text cleaned successfully")
            return result

        except Exception as e:
            self.log(f"Error cleaning text: {e!s}")
            return text

    def get_dataframe(self) -> DataFrame:
        """Return result as DataFrame - only for Text to DataFrame operation."""
        operation = self.get_operation_name()

        # Only return DataFrame for Text to DataFrame operation
        if operation == "Text to DataFrame":
            text = getattr(self, "text_input", "")
            if text:
                return self.text_to_dataframe(text)
            return DataFrame(pd.DataFrame())

        # For all other operations, return empty DataFrame
        return DataFrame(pd.DataFrame())

    def get_text(self) -> Message:
        """Return result as Message - for text operations only."""
        operation = self.get_operation_name()

        # Text operations that should return text
        text_operations = [
            "Case Conversion",
            "Text Replace",
            "Text Extract",
            "Text Head",
            "Text Tail",
            "Text Strip",
            "Text Format",
            "Text Join",
            "Text Clean",
        ]

        if operation in text_operations:
            result = self.process_text()
            if result is not None:
                if isinstance(result, list):
                    message_text = "\n".join(str(item) for item in result)
                else:
                    message_text = str(result)
                return Message(text=message_text)

        return Message(text="")

    def get_data(self) -> Data:
        """Return result as Data object - only for Word Count operation."""
        operation = self.get_operation_name()

        # Only return Data for Word Count operation
        if operation == "Word Count":
            result = self.process_text()
            if result is not None:
                if isinstance(result, dict):
                    return Data(data=result)
                if isinstance(result, list):
                    return Data(data={"items": result})
                return Data(data={"result": str(result)})

        return Data(data={})

    def get_message(self) -> Message:
        """Return result as simple message with just the converted text."""
        result = self.process_text()

        if result is not None:
            if isinstance(result, list):
                message_text = "\n".join(str(item) for item in result)
            else:
                message_text = str(result)
        else:
            message_text = ""

        return Message(text=message_text)

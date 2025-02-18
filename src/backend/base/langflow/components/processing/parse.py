import json
from typing import Any

from langflow.custom import Component
from langflow.helpers.data import data_to_text, data_to_text_list
from langflow.io import (
    HandleInput,
    MultilineInput,
    Output,
    StrInput,
)
from langflow.schema import Data, DataFrame
from langflow.schema.message import Message

INVALID_INPUT_ERROR = "Expected DataFrame or Data object(s)"


class ParseComponent(Component):
    """Parse DataFrames or Data objects into text using templates or default formatting."""

    display_name = "Parse"
    description = "Parse DataFrames or Data objects into text using templates or default formatting."
    icon = "braces"
    name = "Parse"

    inputs = [
        HandleInput(
            name="input_data",
            display_name="Input",
            info="DataFrame or Data object(s) to parse.",
            input_types=["DataFrame", "Data"],
            dynamic=True,
            show=True,
        ),
        MultilineInput(
            name="template_to_parse",
            display_name="Template",
            info="Optional template. Leave empty to include all fields.",
            value="",
            required=False,
        ),
        StrInput(
            name="sep",
            display_name="Separator",
            advanced=True,
            value="\n",
        ),
    ]

    outputs = [
        Output(
            display_name="Parsed Text",
            name="parsed_text",
            info="Combined text with items separated by separator.",
            method="parse_combined_text",
        ),
        Output(
            display_name="Parsed Items",
            name="parsed_items",
            info="List of parsed items.",
            method="parse_as_list",
        ),
    ]

    def _detect_input_type(self) -> str:
        """Detect whether the input is a DataFrame or Data object(s)."""
        if isinstance(self.input_data, DataFrame):
            return "DataFrame"
        if isinstance(self.input_data, (Data, list)) or self.input_data is None:
            return "Data"
        raise ValueError(INVALID_INPUT_ERROR)

    def _handle_dataframe_input(self) -> DataFrame:
        """Handle DataFrame input type."""
        if not isinstance(self.input_data, DataFrame):
            raise ValueError("Expected a DataFrame")
        return self.input_data

    def _handle_data_input(self) -> list[Data]:
        """Handle Data input type."""
        # Convert single Data object or None to list
        if self.input_data is None:
            return []
        if isinstance(self.input_data, Data):
            return [self.input_data]
        if isinstance(self.input_data, list):
            # Filter out None values and validate types
            data_list = [d for d in self.input_data if d is not None]
            if not all(isinstance(d, Data) for d in data_list):
                raise ValueError("Expected Data object(s)")
            return data_list
        raise ValueError("Expected Data object(s)")

    def _format_dataframe_row(self, row: dict[str, Any]) -> str:
        """Format a DataFrame row using the template or default to JSON."""
        if not self.template_to_parse:
            return json.dumps(row, ensure_ascii=False)
        try:
            return self.template_to_parse.format(**row)
        except KeyError:
            return json.dumps(row, ensure_ascii=False)

    def _format_data_object(self, data_obj: Data) -> str:
        """Format a Data object using the template or default formatting."""
        if not self.template_to_parse:
            data_dict = {
                "text": data_obj.text,
                "data": data_obj.data,
            }
            return json.dumps(data_dict, ensure_ascii=False)
        try:
            return self.template_to_parse.format(
                text=data_obj.text,
                data=data_obj.data,
            )
        except KeyError:
            return f"{data_obj.text}"

    def parse_combined_text(self) -> Message:
        """Parse input into a single combined text message."""
        input_type = self._detect_input_type()

        if input_type == "DataFrame":
            df = self._handle_dataframe_input()
            lines = [self._format_dataframe_row(row.to_dict()) for _, row in df.iterrows()]
        else:  # input_type == "Data"
            data = self._handle_data_input()
            if self.template_to_parse and data:
                return Message(text=data_to_text(self.template_to_parse, data, self.sep))
            lines = [self._format_data_object(d) for d in data]

        result = self.sep.join(lines)
        self.status = result
        return Message(text=result)

    def parse_as_list(self) -> list[Data]:
        """Parse input into a list of Data objects."""
        input_type = self._detect_input_type()

        if input_type == "DataFrame":
            df = self._handle_dataframe_input()
            return [Data(text=self._format_dataframe_row(row.to_dict())) for _, row in df.iterrows()]

        # input_type == "Data"
        data = self._handle_data_input()
        if self.template_to_parse and data:
            texts, items = data_to_text_list(self.template_to_parse, data)
            for item, text in zip(items, texts, strict=True):
                item.set_text(text)
            return items

        return [Data(text=self._format_data_object(d)) for d in data]

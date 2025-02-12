import json
from typing import Any

from langflow.custom import Component
from langflow.helpers.data import data_to_text, data_to_text_list
from langflow.io import (
    DataFrameInput,
    DataInput,
    DropdownInput,
    MultilineInput,
    Output,
    StrInput,
)
from langflow.schema import Data, DataFrame
from langflow.schema.message import Message

DATAFRAME_ERROR = "Expected a DataFrame"
DATA_ERROR = "Expected Data object(s)"


class ParseComponent(Component):
    """Parse DataFrames or Data objects into text using templates or default formatting."""

    display_name = "Parse"
    description = "Parse DataFrames or Data objects into text using templates or default formatting."
    icon = "braces"
    name = "Parse"

    inputs = [
        DropdownInput(
            name="parse_input_type",
            display_name="Input Type",
            options=["DataFrame", "Data"],
            value="DataFrame",
            info="Choose whether to parse a DataFrame or Data object(s).",
            required=True,
            real_time_refresh=True,
        ),
        DataFrameInput(
            name="df",
            display_name="DataFrame",
            info="DataFrame to parse.",
            dynamic=True,
            show=True,
        ),
        DataInput(
            name="data",
            display_name="Data",
            info="Data object(s) to parse.",
            dynamic=True,
            show=False,
            is_list=True,
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

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Update the build configuration based on the input type selection."""
        if field_name == "parse_input_type":
            build_config["df"]["show"] = field_value == "DataFrame"
            build_config["data"]["show"] = field_value == "Data"
        return build_config

    def _clean_args(self) -> tuple[DataFrame | None, list[Data], str, str]:
        """Validate and clean input arguments."""
        if self.parse_input_type == "DataFrame":
            if not isinstance(self.df, DataFrame):
                raise ValueError(DATAFRAME_ERROR)
            return self.df, [], self.template_to_parse, self.sep

        # Convert single Data object or None to list
        data_list = [] if self.data is None else (self.data if isinstance(self.data, list) else [self.data])

        # Filter out None values and validate types
        data_list = [d for d in data_list if d is not None]
        if not all(isinstance(d, Data) for d in data_list):
            raise ValueError(DATA_ERROR)

        return None, data_list, self.template_to_parse, self.sep

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
            # Create a dictionary of all available attributes
            data_dict = {
                "text": data_obj.text,
                "data": data_obj.data,
                # Add any other relevant attributes you want to expose
            }
            return json.dumps(data_dict, ensure_ascii=False)
        try:
            return self.template_to_parse.format(
                text=data_obj.text,
                data=data_obj.data,
                # Add other attributes as needed
            )
        except KeyError:
            # Fallback to basic formatting if template fails
            return f"{data_obj.text}"

    def parse_combined_text(self) -> Message:
        """Parse input into a single combined text message."""
        df, data, template_to_parse, sep = self._clean_args()

        if df is not None:
            lines = [self._format_dataframe_row(row.to_dict()) for _, row in df.iterrows()]
        else:
            if template_to_parse:
                # data will never be None here due to _clean_args
                return Message(text=data_to_text(template_to_parse, data, sep))
            lines = [self._format_data_object(d) for d in data]

        result = sep.join(lines)
        self.status = result
        return Message(text=result)

    def parse_as_list(self) -> list[Data]:
        """Parse input into a list of Data objects."""
        df, data, template_to_parse, _ = self._clean_args()

        if df is not None:
            return [Data(text=self._format_dataframe_row(row.to_dict())) for _, row in df.iterrows()]

        if template_to_parse:
            # data will never be None here due to _clean_args
            texts, items = data_to_text_list(template_to_parse, data)
            for item, text in zip(items, texts, strict=True):
                item.set_text(text)
            return items

        return [Data(text=self._format_data_object(d)) for d in data]

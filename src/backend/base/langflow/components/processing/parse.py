import json

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
    display_name = "Parse"
    description = "Parse DataFrames or Data objects into text using templates or default formatting."
    icon = "braces"
    name = "Parse"
    legacy = True

    inputs = [
        DropdownInput(
            name="input_type",
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
            name="template",
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
        if field_name == "input_type":
            build_config["df"]["show"] = field_value == "DataFrame"
            build_config["data"]["show"] = field_value == "Data"
        return build_config

    def _clean_args(self):
        if self.input_type == "DataFrame":
            if not isinstance(self.df, DataFrame):
                err_msg = DATAFRAME_ERROR
                raise ValueError(err_msg)
            return self.df, None, self.template, self.sep

        data = self.data if isinstance(self.data, list) else [self.data]
        if not all(isinstance(d, Data) for d in data if d is not None):
            err_msg = DATA_ERROR
            raise ValueError(err_msg)
        return None, data, self.template, self.sep

    def _format_dataframe_row(self, row: dict) -> str:
        if not self.template:
            return json.dumps(row, ensure_ascii=False)
        try:
            return self.template.format(**row)
        except KeyError:
            return json.dumps(row, ensure_ascii=False)

    def parse_combined_text(self) -> Message:
        df, data, template, sep = self._clean_args()

        if df is not None:
            lines = [self._format_dataframe_row(row.to_dict()) for _, row in df.iterrows()]
        else:
            lines = (
                data_to_text(template, data, sep).split(sep)
                if template
                else [json.dumps(d.__dict__, ensure_ascii=False) for d in data if d]
            )

        result = sep.join(lines)
        self.status = result
        return Message(text=result)

    def parse_as_list(self) -> list[Data]:
        df, data, template, _ = self._clean_args()

        if df is not None:
            return [Data(text=self._format_dataframe_row(row.to_dict())) for _, row in df.iterrows()]

        if template:
            texts, items = data_to_text_list(template, data)
            for item, text in zip(items, texts, strict=True):
                item.set_text(text)
            return items

        return [Data(text=json.dumps(d.__dict__, ensure_ascii=False)) for d in data if d]

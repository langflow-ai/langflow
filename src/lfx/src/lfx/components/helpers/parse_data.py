from typing import Any, Dict, List

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MultilineInput, Output, StrInput
from lfx.schema.data import Data
from langflow.schema.message import Message


class ParseDataComponent(Component):
    display_name = "Parse Data"
    category: str = "helpers"
    description = "Convert a list of dicts (data) into plain text using a template."
    icon = "braces"
    name = "ParseData"

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="The data to convert to text. Should be a list of dicts.",
            is_list=True,
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info="The template to use for formatting the data. Use {key} for keys in the data.",
            value="{text}",
        ),
        StrInput(name="sep", display_name="Separator", advanced=True, value="\n"),
    ]

    outputs = [
        Output(
            display_name="Text",
            name="text",
            info="Data as a single Message, with each input data separated by Separator",
            method="parse_data",
        ),
        Output(
            display_name="Data List",
            name="data_list",
            info="Data as a list of dicts, each having `text` formatted by Template",
            method="parse_data_as_list",
        ),
        Output(
            display_name="Data Object List",
            name="data_object_list",
            info="Data as a list of Data objects, each having `text` formatted by Template (for compatibility)",
            method="parse_data_as_data_list",
        ),
    ]

    def _clean_args(self) -> tuple[List[Dict[str, Any]], str, str]:
        data = self.data if isinstance(self.data, list) else [self.data]
        template = self.template
        sep = self.sep
        return data, template, sep

    def parse_data(self) -> Message:
        data, template, sep = self._clean_args()
        result_string = self.data_to_text(template, data, sep)
        self.status = result_string
        return Message(text=result_string)

    def parse_data_as_list(self) -> List[Dict[str, Any]]:
        data, template, _ = self._clean_args()
        text_list, data_list = self.data_to_text_list(template, data)
        for item, text in zip(data_list, text_list, strict=True):
            item["text"] = text
        self.status = data_list
        return data_list

    def parse_data_as_data_list(self) -> List["Data"]:
        data, template, _ = self._clean_args()
        text_list, data_list = self.data_to_text_list(template, data)
        for item, text in zip(data_list, text_list, strict=True):
            item["text"] = text
        self.status = data_list
        return [Data(value=item) for item in data_list]

    @staticmethod
    def data_to_text(template: str, data: List[Dict[str, Any]], sep: str) -> str:
        formatted = []
        for item in data:
            try:
                formatted.append(template.format(**item))
            except Exception:
                formatted.append(str(item))
        return sep.join(formatted)

    @staticmethod
    def data_to_text_list(template: str, data: List[Dict[str, Any]]):
        text_list = []
        data_list = []
        for item in data:
            try:
                text = template.format(**item)
            except Exception:
                text = str(item)
            text_list.append(text)
            data_list.append(dict(item))
        return text_list, data_list

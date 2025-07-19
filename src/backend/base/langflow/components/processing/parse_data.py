from lfx.custom.custom_component.component import Component

from langflow.helpers.data import data_to_text, data_to_text_list
from langflow.io import DataInput, MultilineInput, Output, StrInput
from langflow.schema.data import Data
from langflow.schema.message import Message


class ParseDataComponent(Component):
    display_name = "Data to Message"
    description = "Convert Data objects into Messages using any {field_name} from input data."
    icon = "message-square"
    name = "ParseData"
    legacy = True
    metadata = {
        "legacy_name": "Parse Data",
    }

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="The data to convert to text.",
            is_list=True,
            required=True,
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info="The template to use for formatting the data. "
            "It can contain the keys {text}, {data} or any other key in the Data.",
            value="{text}",
            required=True,
        ),
        StrInput(name="sep", display_name="Separator", advanced=True, value="\n"),
    ]

    outputs = [
        Output(
            display_name="Message",
            name="text",
            info="Data as a single Message, with each input Data separated by Separator",
            method="parse_data",
        ),
        Output(
            display_name="Data List",
            name="data_list",
            info="Data as a list of new Data, each having `text` formatted by Template",
            method="parse_data_as_list",
        ),
    ]

    def _clean_args(self) -> tuple[list[Data], str, str]:
        data = self.data if isinstance(self.data, list) else [self.data]
        template = self.template
        sep = self.sep
        return data, template, sep

    def parse_data(self) -> Message:
        data, template, sep = self._clean_args()
        result_string = data_to_text(template, data, sep)
        self.status = result_string
        return Message(text=result_string)

    def parse_data_as_list(self) -> list[Data]:
        data, template, _ = self._clean_args()
        text_list, data_list = data_to_text_list(template, data)
        for item, text in zip(data_list, text_list, strict=True):
            item.set_text(text)
        self.status = data_list
        return data_list

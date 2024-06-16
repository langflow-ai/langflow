from langflow.custom import Component
from langflow.helpers.data import data_to_text
from langflow.field_typing import Text
from langflow.inputs import MultilineInput, HandleInput
from langflow.template import Output


class ParseDataComponent(Component):
    display_name = "Parse Data"
    description = "Convert Data into plain text following a specified template."
    icon = "braces"

    inputs = [
        HandleInput(
            name="data", display_name="Data", info="The data to convert to text.", input_types=["Data"]
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info="The template to use for formatting the data. It can contain the keys {text}, {data} or any other key in the Data.",
        ),
    ]

    outputs = [
        Output(display_name="Text", name="text", method="parse_data_to_text"),
    ]

    def parse_data_to_text(self) -> Text:
        data = self.data if isinstance(self.data, list) else [self.data]
        template = self.template

        result_string = data_to_text(template, data)
        self.status = result_string
        return result_string

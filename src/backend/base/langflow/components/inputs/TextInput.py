from langflow.base.io.text import TextComponent
from langflow.field_typing import Text
from langflow.template import Input, Output


class TextInput(TextComponent):
    display_name = "Text Input"
    description = "Get text inputs from the Playground."
    icon = "type"

    inputs = [
        Input(
            name="input_value",
            type=str,
            display_name="Value",
            info="Text or Data to be passed as input.",
            input_types=["Data", "Text"],
        ),
        Input(
            name="record_template",
            type=str,
            display_name="Data Template",
            multiline=True,
            info="Template to convert Data to Text. If left empty, it will be dynamically set to the Data's text key.",
            advanced=True,
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text", method="text_response"),
    ]

    def text_response(self) -> Text:
        return self.build(input_value=self.input_value, record_template=self.record_template)

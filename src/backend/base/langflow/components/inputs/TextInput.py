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
            info="Text or Record to be passed as input.",
            input_types=["Record", "Text"],
        ),
        Input(
            name="record_template",
            type=str,
            display_name="Record Template",
            multiline=True,
            info="Template to convert Record to Text. If left empty, it will be dynamically set to the Record's text key.",
            advanced=True,
        ),
    ]
    outputs = [
        Output(name="Text", method="text_response"),
    ]

    def text_response(self) -> Text:
        return self.input_value if self.input_value else ""

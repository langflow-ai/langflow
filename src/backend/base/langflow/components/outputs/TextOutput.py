from langflow.base.io.text import TextComponent
from langflow.field_typing import Text
from langflow.template import Input, Output


class TextOutput(TextComponent):
    display_name = "Text Output"
    description = "Display a text output in the Playground."
    icon = "type"

    inputs = [
        Input(
            name="input_value",
            type=str,
            display_name="Value",
            info="Text or Record to be passed as output.",
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
        Output(display_name="Text", name="text", method="text_response"),
    ]

    def text_response(self) -> Text:
        return self.build(input_value=self.input_value, record_template=self.record_template)

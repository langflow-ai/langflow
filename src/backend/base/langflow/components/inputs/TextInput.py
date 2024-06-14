from langflow.base.io.text import TextComponent
from langflow.field_typing import Text
from langflow.inputs import MultilineInput, StrInput
from langflow.template import Output


class TextInputComponent(TextComponent):
    display_name = "Text Input"
    description = "Get text inputs from the Playground."
    icon = "type"

    inputs = [
        StrInput(
            name="input_value",
            display_name="Text",
            info="Text to be passed as input.",
        ),
        MultilineInput(
            name="data_template",
            display_name="Data Template",
            info="Template to convert Data to Text. If left empty, it will be dynamically set to the Data's text key.",
            advanced=True,
            value="{text}",
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text", method="text_response"),
    ]

    def text_response(self) -> Text:
        return self.build(input_value=self.input_value, data_template=self.data_template)

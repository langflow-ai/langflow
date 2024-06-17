from langflow.base.io.text import TextComponent
from langflow.field_typing import Text
from langflow.inputs import TextInput
from langflow.template import Output


class TextInputComponent(TextComponent):
    display_name = "Text Input"
    description = "Get text inputs from the Playground."
    icon = "type"

    inputs = [
        TextInput(
            name="input_value",
            display_name="Text",
            info="Text to be passed as input.",
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text", method="text_response"),
    ]

    def text_response(self) -> Text:
        return self.build(input_value=self.input_value)

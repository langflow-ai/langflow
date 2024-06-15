from langflow.base.io.text import TextComponent
from langflow.field_typing import Text
from langflow.template import Output
from langflow.inputs import StrInput


class TextOutputComponent(TextComponent):
    display_name = "Text Output"
    description = "Display a text output in the Playground."
    icon = "type"

    inputs = [
        StrInput(
            name="input_value",
            display_name="Text",
            info="Text or Data to be passed as output.",
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text", method="text_response"),
    ]

    def text_response(self) -> Text:
        return self.build(input_value=self.input_value)

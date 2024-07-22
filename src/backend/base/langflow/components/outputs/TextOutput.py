from langflow.base.io.text import TextComponent
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class TextOutputComponent(TextComponent):
    display_name = "Text Output"
    description = "Display a text output in the Playground."
    icon = "type"
    name = "TextOutput"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Text",
            info="Text to be passed as output.",
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text", method="text_response"),
    ]

    def text_response(self) -> Message:
        message = Message(
            text=self.input_value,
        )
        self.status = self.input_value
        return message

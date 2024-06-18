from langflow.base.io.text import TextComponent
from langflow.template import Output
from langflow.inputs import TextInput
from langflow.schema.message import Message


class TextOutputComponent(TextComponent):
    display_name = "Text Output"
    description = "Display a text output in the Playground."
    icon = "type"

    inputs = [
        TextInput(
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
            sender=self.sender,
            sender_name=self.sender_name,
            session_id=self.session_id,
        )
        return message

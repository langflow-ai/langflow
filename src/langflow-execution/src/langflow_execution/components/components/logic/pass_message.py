from langflow.custom import Component
from langflow.io import MessageInput
from langflow.schema.message import Message
from langflow.template import Output


class PassMessageComponent(Component):
    display_name = "Pass"
    description = "Forwards the input message, unchanged."
    name = "Pass"
    icon = "arrow-right"

    inputs = [
        MessageInput(
            name="input_message",
            display_name="Input Message",
            info="The message to be passed forward.",
            required=True,
        ),
        MessageInput(
            name="ignored_message",
            display_name="Ignored Message",
            info="A second message to be ignored. Used as a workaround for continuity.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Output Message", name="output_message", method="pass_message"),
    ]

    def pass_message(self) -> Message:
        self.status = self.input_message
        return self.input_message

from lfx.custom.custom_component.component import Component
from lfx.io import MessageInput
from lfx.schema.message import Message
from lfx.template.field.base import Output


class PassMessageComponent(Component):
    component_id: str = "0a4a6987-7ad1-4448-8b06-13e90ca94fcb"
    display_name = "Pass"
    description = "Forwards the input message, unchanged."
    name = "Pass"
    icon = "arrow-right"
    legacy: bool = True
    replacement = ["logic.ConditionalRouter"]

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

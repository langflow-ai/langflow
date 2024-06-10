from langflow.base.io.chat import ChatComponent
from langflow.field_typing import Text
from langflow.schema.message import Message
from langflow.template import Input, Output


class ChatOutput(ChatComponent):
    display_name = "Chat Output"
    description = "Display a chat message in the Playground."
    icon = "ChatOutput"

    inputs = [
        Input(
            name="input_value", type=str, display_name="Text", multiline=True, info="Message to be passed as output."
        ),
        Input(
            name="sender",
            type=str,
            display_name="Sender Type",
            options=["Machine", "User"],
            value="Machine",
            advanced=True,
            info="Type of sender.",
        ),
        Input(name="sender_name", type=str, display_name="Sender Name", info="Name of the sender.", value="AI"),
        Input(
            name="session_id", type=str, display_name="Session ID", info="Session ID for the message.", advanced=True
        ),
        Input(
            name="record_template",
            type=str,
            display_name="Record Template",
            value="{text}",
            advanced=True,
            info="Template to convert Record to Text. If left empty, it will be dynamically set to the Record's text key.",
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text", method="text_response"),
        Output(display_name="Message", name="message", method="message_response"),
    ]

    def text_response(self) -> Text:
        result = self.input_value
        if self.session_id and isinstance(result, (Message, str)):
            self.store_message(result, self.session_id, self.sender, self.sender_name)
        return result

    def message_response(self) -> Message:
        message = Message(
            text=self.input_value,
            sender=self.sender,
            sender_name=self.sender_name,
            session_id=self.session_id,
        )
        if self.session_id and isinstance(message, (Message, str)):
            self.store_message(message)
        self.status = message
        return message

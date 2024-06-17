from langflow.base.io.chat import ChatComponent
from langflow.field_typing import Text
from langflow.inputs import DropdownInput, TextInput
from langflow.schema.message import Message
from langflow.template import Output


class ChatInput(ChatComponent):
    display_name = "Chat Input"
    description = "Get chat inputs from the Playground."
    icon = "ChatInput"

    inputs = [
        TextInput(
            name="input_value",
            display_name="Text",
            multiline=True,
            input_types=[],
            value="",
            info="Message to be passed as input.",
        ),
        DropdownInput(
            name="sender",
            display_name="Sender Type",
            options=["Machine", "User"],
            value="User",
            info="Type of sender.",
            advanced=True,
        ),
        TextInput(
            name="sender_name",
            type=str,
            display_name="Sender Name",
            info="Name of the sender.",
            value="User",
            advanced=True,
        ),
        TextInput(
            name="session_id", type=str, display_name="Session ID", info="Session ID for the message.", advanced=True
        ),
    ]
    outputs = [
        Output(display_name="Message", name="message", method="message_response"),
        Output(display_name="Text", name="text", method="text_response"),
    ]

    def message_response(self) -> Message:
        message = Message(
            text=self.input_value,
            sender=self.sender,
            sender_name=self.sender_name,
            session_id=self.session_id,
        )
        if self.session_id and isinstance(message, Message) and isinstance(message.text, str):
            self.store_message(message)
            self.message.value = message

        self.status = message
        return message

    def text_response(self) -> Text:
        text = self.message_response().text
        return text

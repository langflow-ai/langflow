from langflow.base.io.chat import ChatComponent
from langflow.inputs import BoolInput, DropdownInput, MultilineInput, StrInput
from langflow.schema.message import Message
from langflow.template import Output


class ChatOutput(ChatComponent):
    display_name = "Chat Output"
    description = "Display a chat message in the Playground."
    icon = "ChatOutput"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Text",
            info="Message to be passed as output.",
            input_types=["Text", "Message"],
        ),
        DropdownInput(
            name="sender",
            display_name="Sender Type",
            options=["Machine", "User"],
            value="Machine",
            advanced=True,
            info="Type of sender.",
        ),
        StrInput(name="sender_name", display_name="Sender Name", info="Name of the sender.", value="AI", advanced=True),
        StrInput(name="session_id", display_name="Session ID", info="Session ID for the message.", advanced=True),
        BoolInput(
            name="data_template",
            display_name="Data Template",
            value="{text}",
            advanced=True,
            info="Template to convert Data to Text. If left empty, it will be dynamically set to the Data's text key.",
        ),
    ]
    outputs = [
        Output(display_name="Message", name="message", method="message_response"),
    ]

    def message_response(self) -> Message:
        if isinstance(self.input_value, Message):
            message = self.input_value
        else:
            message = Message(
                text=self.input_value,
                sender=self.sender,
                sender_name=self.sender_name,
                session_id=self.session_id,
            )
        if self.session_id and isinstance(message, Message) and isinstance(message.text, str):
            self.store_message(message)
        self.status = message
        return message

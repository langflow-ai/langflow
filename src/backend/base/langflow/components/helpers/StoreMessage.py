from langflow.custom import Component
from langflow.inputs import MessageInput, StrInput
from langflow.schema.message import Message
from langflow.template import Output
from langflow.memory import get_messages, store_message


class StoreMessageComponent(Component):
    display_name = "Store Message"
    description = "Stores a chat message or text."
    icon = "save"

    inputs = [
        MessageInput(name="message", display_name="Message", info="The chat message to be stored.", required=True),
        StrInput(
            name="sender",
            display_name="Sender",
            info="The sender of the message.",
            value="AI",
            advanced=True,
        ),
        StrInput(
            name="sender_name", display_name="Sender Name", info="The name of the sender.", value="AI", advanced=True
        ),
        StrInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID of the chat.",
            value="",
        ),
    ]

    outputs = [
        Output(display_name="Stored Messages", name="stored_messages", method="store_message"),
    ]

    def store_message(self) -> Message:
        message = self.message

        message.session_id = self.session_id or message.session_id
        message.sender = self.sender or message.sender
        message.sender_name = self.sender_name or message.sender_name

        store_message(message, flow_id=self.graph.flow_id)
        stored = get_messages(session_id=message.session_id, sender_name=message.sender_name, sender=message.sender)
        self.status = stored
        return stored

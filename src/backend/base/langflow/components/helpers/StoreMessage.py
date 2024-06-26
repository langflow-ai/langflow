from langflow.custom import Component
from langflow.inputs import MessageTextInput, StrInput
from langflow.schema.message import Message
from langflow.template import Output
from langflow.memory import get_messages, store_message


class StoreMessageComponent(Component):
    display_name = "Store Message"
    description = "Stores a chat message or text."
    icon = "save"

    inputs = [
        MessageTextInput(
            name="message",
            display_name="Message",
            info="The chat message to be stored.",
            input_types=["Message", "str"],
            required=True,
        ),
        StrInput(
            name="sender",
            display_name="Sender",
            info="The sender of the message.",
            value="",
            advanced=True,
        ),
        StrInput(
            name="sender_name", display_name="Sender Name", info="The name of the sender.", value="", advanced=True
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
        if isinstance(self.message, str):
            if not self.session_id:
                raise ValueError("If passing a text, Session ID cannot be empty.")
            message = Message(
                text=self.message, sender=self.sender, sender_name=self.sender_name, session_id=self.session_id
            )

        elif isinstance(self.message, Message):
            message = self.message
            if self.session_id:
                message.session_id = self.session_id
            if self.sender:
                message.sender = self.sender
            if self.sender_name:
                message.sender_name = self.sender_name
        else:
            raise ValueError("Message should be either string or Message.")

        store_message(message, flow_id=self.graph.flow_id)

        stored = get_messages(session_id=message.session_id, sender_name=message.sender_name, sender=message.sender)
        self.status = stored
        return stored

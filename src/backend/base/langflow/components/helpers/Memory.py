from langflow.custom import Component
from langflow.inputs import DropdownInput, IntInput, TextInput
from langflow.memory import get_messages
from langflow.schema import Data
from langflow.schema.message import Message
from langflow.template import Output


class MemoryComponent(Component):
    display_name = "Memory"
    description = "Retrieves stored chat messages."
    icon = "history"

    inputs = [
        DropdownInput(
            name="sender",
            display_name="Sender Type",
            options=["Machine", "User", "Machine and User"],
            value="Machine and User",
            info="Type of sender.",
            advanced=True,
        ),
        TextInput(
            name="sender_name",
            display_name="Sender Name",
            info="Name of the sender.",
            advanced=True,
        ),
        IntInput(
            name="n_messages",
            display_name="Number of Messages",
            value=100,
            info="Number of messages to retrieve.",
            advanced=True,
        ),
        TextInput(
            name="session_id",
            display_name="Session ID",
            info="Session ID of the chat history.",
            advanced=True,
        ),
        DropdownInput(
            name="order",
            display_name="Order",
            options=["Ascending", "Descending"],
            value="Ascending",
            info="Order of the messages.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Message Data", name="messages", method="retrieve_messages"),
        Output(display_name="Parsed", name="messages_text", method="retrieve_messages_as_text"),
    ]

    def retrieve_messages(self) -> Data:
        sender = self.sender
        sender_name = self.sender_name
        session_id = self.session_id
        n_messages = self.n_messages
        order = "DESC" if self.order == "Descending" else "ASC"

        if sender == "Machine and User":
            sender = None

        messages = get_messages(
            sender=sender,
            sender_name=sender_name,
            session_id=session_id,
            limit=n_messages,
            order=order,
        )
        self.status = messages
        return messages

    def retrieve_messages_as_text(self) -> Message:
        messages = self.retrieve_messages()
        messages_text = "\n".join(
            [f"{message.data.get('sender_name')}: {message.data.get('text')}" for message in messages]
        )
        self.status = messages_text
        return Message(text=messages_text)

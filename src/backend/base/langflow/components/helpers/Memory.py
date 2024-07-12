from langflow.custom import Component
from langflow.helpers.data import data_to_text
from langflow.io import DropdownInput, IntInput, MessageTextInput, MultilineInput, Output
from langflow.memory import get_messages
from langflow.schema import Data
from langflow.schema.message import Message


class MemoryComponent(Component):
    display_name = "Chat Memory"
    description = "Retrieves stored chat messages."
    icon = "message-square-more"

    inputs = [
        DropdownInput(
            name="sender",
            display_name="Sender Type",
            options=["Machine", "User", "Machine and User"],
            value="Machine and User",
            info="Type of sender.",
            advanced=True,
        ),
        MessageTextInput(
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
        MessageTextInput(
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
        MultilineInput(
            name="template",
            display_name="Template",
            info="The template to use for formatting the data. It can contain the keys {text}, {sender} or any other key in the message data.",
            value="{sender_name}: {text}",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Chat History", name="messages", method="retrieve_messages"),
        Output(display_name="Messages (Text)", name="messages_text", method="retrieve_messages_as_text"),
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
        messages_text = data_to_text(self.template, self.retrieve_messages())
        self.status = messages_text
        return Message(text=messages_text)

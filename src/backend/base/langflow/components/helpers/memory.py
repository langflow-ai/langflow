from langflow.custom import Component
from langflow.helpers.data import data_to_text
from langflow.inputs import HandleInput
from langflow.io import DropdownInput, IntInput, MessageTextInput, MultilineInput, Output
from langflow.memory import aget_messages
from langflow.schema import Data
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER


class MemoryComponent(Component):
    display_name = "Message History"
    description = "Retrieves stored chat messages from Langflow tables or an external memory."
    icon = "message-square-more"
    name = "Memory"

    inputs = [
        HandleInput(
            name="memory",
            display_name="External Memory",
            input_types=["Memory"],
            info="Retrieve messages from an external memory. If empty, it will use the Langflow tables.",
        ),
        DropdownInput(
            name="sender",
            display_name="Sender Type",
            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER, "Machine and User"],
            value="Machine and User",
            info="Filter by sender type.",
            advanced=True,
        ),
        MessageTextInput(
            name="sender_name",
            display_name="Sender Name",
            info="Filter by sender name.",
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
            info="The session ID of the chat. If empty, the current session ID parameter will be used.",
            advanced=True,
        ),
        DropdownInput(
            name="order",
            display_name="Order",
            options=["Ascending", "Descending"],
            value="Ascending",
            info="Order of the messages.",
            advanced=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info="The template to use for formatting the data. "
            "It can contain the keys {text}, {sender} or any other key in the message data.",
            value="{sender_name}: {text}",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="messages", method="retrieve_messages"),
        Output(display_name="Text", name="messages_text", method="retrieve_messages_as_text"),
    ]

    async def retrieve_messages(self) -> Data:
        sender = self.sender
        sender_name = self.sender_name
        session_id = self.session_id
        n_messages = self.n_messages
        order = "DESC" if self.order == "Descending" else "ASC"

        if sender == "Machine and User":
            sender = None

        if self.memory:
            # override session_id
            self.memory.session_id = session_id

            stored = await self.memory.aget_messages()
            # langchain memories are supposed to return messages in ascending order
            if order == "DESC":
                stored = stored[::-1]
            if n_messages:
                stored = stored[:n_messages]
            stored = [Message.from_lc_message(m) for m in stored]
            if sender:
                expected_type = MESSAGE_SENDER_AI if sender == MESSAGE_SENDER_AI else MESSAGE_SENDER_USER
                stored = [m for m in stored if m.type == expected_type]
        else:
            stored = await aget_messages(
                sender=sender,
                sender_name=sender_name,
                session_id=session_id,
                limit=n_messages,
                order=order,
            )
        self.status = stored
        return stored

    async def retrieve_messages_as_text(self) -> Message:
        stored_text = data_to_text(self.template, await self.retrieve_messages())
        self.status = stored_text
        return Message(text=stored_text)

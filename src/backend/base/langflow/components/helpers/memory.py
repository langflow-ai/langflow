from typing import Any, cast

from langflow.custom import Component
from langflow.inputs import HandleInput
from langflow.io import DropdownInput, IntInput, MessageTextInput, MultilineInput, Output, TabInput
from langflow.memory import aget_messages, astore_message
from langflow.schema import Data, dotdict
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.utils.component_utils import set_current_fields, set_field_display
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI, MESSAGE_SENDER_USER


class MemoryComponent(Component):
    display_name = "Message History"
    description = "Stores or retrieves stored chat messages from Langflow tables or an external memory."
    icon = "message-square-more"
    name = "Memory"
    default_keys = ["mode", "memory"]
    mode_config = {
        "Store": ["message", "memory", "sender", "sender_name", "session_id"],
        "Retrieve": ["n_messages", "order", "template", "memory"],
    }

    inputs = [
        TabInput(
            name="mode",
            display_name="Mode",
            options=["Retrieve", "Store"],
            value="Retrieve",
            info="Operation mode: Store messages or Retrieve messages.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="message",
            display_name="Message",
            info="The chat message to be stored.",
            tool_mode=True,
            dynamic=True,
            show=False,
        ),
        HandleInput(
            name="memory",
            display_name="External Memory",
            input_types=["Memory"],
            info="Retrieve messages from an external memory. If empty, it will use the Langflow tables.",
            advanced=True,
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
            show=False,
        ),
        IntInput(
            name="n_messages",
            display_name="Number of Messages",
            value=100,
            info="Number of messages to retrieve.",
            advanced=True,
            show=False,
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
            required=True,
            show=False,
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info="The template to use for formatting the data. "
            "It can contain the keys {text}, {sender} or any other key in the message data.",
            value="{sender_name}: {text}",
            advanced=True,
            show=False,
        ),
    ]

    outputs = [Output(display_name="Messages", name="dataframe", method="retrieve_messages_dataframe", dynamic=True)]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant output based on the selected output type."""
        if field_name == "mode":
            # Start with empty outputs
            frontend_node["outputs"] = []
            if field_value == "Store":
                frontend_node["outputs"] = [
                    Output(
                        display_name="Stored Messages",
                        name="stored_messages",
                        method="store_message",
                        hidden=True,
                        dynamic=True,
                    )
                ]
            if field_value == "Retrieve":
                frontend_node["outputs"] = [
                    Output(
                        display_name="Messages", name="dataframe", method="retrieve_messages_dataframe", dynamic=True
                    )
                ]
        return frontend_node

    async def retrieve_messages(self) -> Data:
        sender = self.sender
        sender_name = self.sender_name
        session_id = self.session_id
        n_messages = self.n_messages
        order = "DESC" if self.order == "Descending" else "ASC"

        if sender == "Machine and User":
            sender = None

        if self.memory and not hasattr(self.memory, "aget_messages"):
            memory_name = type(self.memory).__name__
            err_msg = f"External Memory object ({memory_name}) must have 'aget_messages' method."
            raise AttributeError(err_msg)
        # Check if n_messages is None or 0
        if n_messages == 0:
            stored = []
        elif self.memory:
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
        return cast(Data, stored)

    async def retrieve_messages_dataframe(self) -> DataFrame:
        """Convert the retrieved messages into a DataFrame.

        Returns:
            DataFrame: A DataFrame containing the message data.
        """
        messages = await self.retrieve_messages()
        return DataFrame(messages)

    async def store_message(self) -> Message:
        message = Message(text=self.message) if isinstance(self.message, str) else self.message

        message.session_id = self.session_id or message.session_id
        message.sender = self.sender or message.sender or MESSAGE_SENDER_AI
        message.sender_name = self.sender_name or message.sender_name or MESSAGE_SENDER_NAME_AI

        stored_messages: list[Message] = []

        if self.memory:
            self.memory.session_id = message.session_id
            lc_message = message.to_lc_message()
            await self.memory.aadd_messages([lc_message])

            stored_messages = await self.memory.aget_messages() or []

            stored_messages = [Message.from_lc_message(m) for m in stored_messages] if stored_messages else []

            if message.sender:
                stored_messages = [m for m in stored_messages if m.sender == message.sender]
        else:
            await astore_message(message, flow_id=self.graph.flow_id)
            stored_messages = (
                await aget_messages(
                    session_id=message.session_id, sender_name=message.sender_name, sender=message.sender
                )
                or []
            )

        if not stored_messages:
            msg = "No messages were stored. Please ensure that the session ID and sender are properly set."
            raise ValueError(msg)

        stored_message = stored_messages[0]
        self.status = stored_message
        return stored_message

    def update_build_config(
        self,
        build_config: dotdict,
        field_value: Any,  # noqa: ARG002
        field_name: str | None = None,  # noqa: ARG002
    ) -> dotdict:
        return set_current_fields(
            build_config=build_config,
            action_fields=self.mode_config,
            selected_action=build_config["mode"]["value"],
            default_fields=self.default_keys,
            func=set_field_display,
        )

import asyncio
from typing import AsyncIterator, Iterator, Optional, Union

from langflow.custom import Component
from langflow.memory import store_message
from langflow.schema import Data
from langflow.schema.message import Message
from langflow.services.database.models.message.crud import update_message


class ChatComponent(Component):
    display_name = "Chat Component"
    description = "Use as base for chat components."

    # Keep this method for backward compatibility
    def store_message(
        self,
        message: Message,
    ) -> list[Message]:
        messages = store_message(
            message,
            flow_id=self.graph.flow_id,
        )

        self.status = messages
        return messages

    def build_with_data(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "User",
        input_value: Optional[Union[str, Data, Message]] = None,
        files: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        return_message: Optional[bool] = False,
    ) -> Message:
        message: Message | None = None

        if isinstance(input_value, Data):
            # Update the data of the record
            message = Message.from_data(input_value)
        else:
            message = Message(
                text=input_value, sender=sender, sender_name=sender_name, files=files, session_id=session_id
            )
        if not return_message:
            message_text = message.text
        else:
            message_text = message  # type: ignore

        self.status = message_text
        if session_id and isinstance(message, Message) and isinstance(message.text, str):
            messages = store_message(
                message,
                flow_id=self.graph.flow_id,
            )
            self.status = messages
        return message_text  # type: ignore

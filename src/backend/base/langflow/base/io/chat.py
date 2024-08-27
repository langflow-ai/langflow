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
    ) -> Message:
        messages = store_message(
            message,
            flow_id=self.graph.flow_id,
        )
        if len(messages) > 1:
            raise ValueError("Only one message can be stored at a time.")
        stored_message = messages[0]
        if hasattr(self, "_event_manager") and self._event_manager and stored_message.id:
            if not isinstance(message.text, str):
                complete_message = self._stream_message(message, stored_message.id)
                message_table = update_message(message_id=stored_message.id, message=dict(text=complete_message))
                stored_message = Message(**message_table.model_dump())
                self.vertex._added_message = stored_message
        self.status = stored_message
        return stored_message

    def _stream_message(self, message: Message, message_id: str):
        iterator = message.text
        if not isinstance(iterator, (AsyncIterator, Iterator)):
            raise ValueError("The message must be an iterator or an async iterator.")
        complete_message: str = ""
        if isinstance(iterator, AsyncIterator):
            iterator = asyncio.ensure_future(iterator.__anext__())
        self._log_callback("start_message", {"text": "",
                                             "sender": message.sender,
                                             "sender_name": message.sender_name,
                                             "id": str(message_id),
                                             "timestamp": message.timestamp,
                                             "flow_id": self.graph.flow_id,
                                             "session_id": message.session_id,
                                             "files": message.files,
                                             })
        for chunk in iterator:
            complete_message += chunk.content
            data = {
                "text": complete_message,
                "chunk": chunk.content,
                "sender": message.sender,
                "sender_name": message.sender_name,
                "id": str(message_id),
            }
            self._event_manager.on_token(data)
        return complete_message

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

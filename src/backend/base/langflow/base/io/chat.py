from typing import AsyncIterator, Iterator, Optional, Union

from langflow.custom import Component
from langflow.memory import store_message
from langflow.schema import Data
from langflow.schema.message import Message
from langflow.services.database.models.message.crud import update_message
from langflow.utils.async_helpers import run_until_complete


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

    def _process_chunk(self, chunk: str, complete_message: str, message: Message, message_id: str) -> str:
        complete_message += chunk
        data = {
            "text": complete_message,
            "chunk": chunk,
            "sender": message.sender,
            "sender_name": message.sender_name,
            "id": str(message_id),
        }
        if self._event_manager:
            self._event_manager.on_token(data=data)
        return complete_message

    async def _handle_async_iterator(self, iterator: AsyncIterator, message: Message, message_id: str) -> str:
        complete_message = ""
        async for chunk in iterator:
            complete_message = self._process_chunk(chunk.content, complete_message, message, message_id)
        return complete_message

    def _stream_message(self, message: Message, message_id: str) -> str:
        iterator = message.text
        if not isinstance(iterator, (AsyncIterator, Iterator)):
            raise ValueError("The message must be an iterator or an async iterator.")

        if isinstance(iterator, AsyncIterator):
            return run_until_complete(self._handle_async_iterator(iterator, message, message_id))

        complete_message = ""
        for chunk in iterator:
            complete_message = self._process_chunk(chunk.content, complete_message, message, message_id)

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

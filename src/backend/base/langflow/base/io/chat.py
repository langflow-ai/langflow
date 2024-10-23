from collections.abc import AsyncIterator, Iterator
from typing import cast

from langflow.custom import Component
from langflow.memory import store_message
from langflow.schema import Data
from langflow.schema.message import Message
from langflow.services.database.models.message.crud import update_message
from langflow.utils.async_helpers import run_until_complete


class ChatComponent(Component):
    display_name = "Chat Component"
    description = "Use as base for chat components."

    def store_message(self, message: Message) -> Message:
        messages = store_message(message, flow_id=self.graph.flow_id)
        if len(messages) != 1:
            msg = "Only one message can be stored at a time."
            raise ValueError(msg)

        stored_message = messages[0]
        self._send_message_event(stored_message)

        if self._should_stream_message(stored_message, message):
            complete_message = self._stream_message(message, stored_message.id)
            stored_message = self._update_stored_message(stored_message.id, complete_message)

        self.status = stored_message
        return stored_message

    def _send_message_event(self, message: Message) -> None:
        if hasattr(self, "_event_manager") and self._event_manager:
            self._event_manager.on_message(data=message.data)

    def _should_stream_message(self, stored_message: Message, original_message: Message) -> bool:
        return bool(
            hasattr(self, "_event_manager")
            and self._event_manager
            and stored_message.id
            and not isinstance(original_message.text, str)
        )

    def _update_stored_message(self, message_id: str, complete_message: str) -> Message:
        message_table = update_message(message_id=message_id, message={"text": complete_message})
        updated_message = Message(**message_table.model_dump())
        self.vertex.added_message = updated_message
        return updated_message

    def _process_chunk(self, chunk: str, complete_message: str, message: Message, message_id: str) -> str:
        complete_message += chunk
        if self._event_manager:
            self._event_manager.on_token(
                data={
                    "text": complete_message,
                    "chunk": chunk,
                    "sender": message.sender,
                    "sender_name": message.sender_name,
                    "id": str(message_id),
                }
            )
        return complete_message

    async def _handle_async_iterator(self, iterator: AsyncIterator, message: Message, message_id: str) -> str:
        complete_message = ""
        async for chunk in iterator:
            complete_message = self._process_chunk(chunk.content, complete_message, message, message_id)
        return complete_message

    def _stream_message(self, message: Message, message_id: str) -> str:
        iterator = message.text
        if not isinstance(iterator, AsyncIterator | Iterator):
            msg = "The message must be an iterator or an async iterator."
            raise TypeError(msg)

        if isinstance(iterator, AsyncIterator):
            return run_until_complete(self._handle_async_iterator(iterator, message, message_id))

        complete_message = ""
        for chunk in iterator:
            complete_message = self._process_chunk(chunk.content, complete_message, message, message_id)
        return complete_message

    def build_with_data(
        self,
        *,
        sender: str | None = "User",
        sender_name: str | None = "User",
        input_value: str | Data | Message | None = None,
        files: list[str] | None = None,
        session_id: str | None = None,
        return_message: bool = False,
    ) -> str | Message:
        message = self._create_message(input_value, sender, sender_name, files, session_id)
        message_text = message.text if not return_message else message

        self.status = message_text
        if session_id and isinstance(message, Message) and isinstance(message.text, str):
            messages = store_message(message, flow_id=self.graph.flow_id)
            self.status = messages
            self._send_messages_events(messages)

        return cast(str | Message, message_text)

    def _create_message(self, input_value, sender, sender_name, files, session_id) -> Message:
        if isinstance(input_value, Data):
            return Message.from_data(input_value)
        return Message(text=input_value, sender=sender, sender_name=sender_name, files=files, session_id=session_id)

    def _send_messages_events(self, messages) -> None:
        if hasattr(self, "_event_manager") and self._event_manager:
            for stored_message in messages:
                self._event_manager.on_message(data=stored_message.data)

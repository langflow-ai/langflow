from typing import cast

from langflow.custom import Component
from langflow.memory import store_message
from langflow.schema import Data
from langflow.schema.message import Message


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
        return Message(
            text=input_value,
            sender=sender,
            sender_name=sender_name,
            files=files,
            session_id=session_id,
            category="message",
        )

    def _send_messages_events(self, messages) -> None:
        if hasattr(self, "_event_manager") and self._event_manager:
            for stored_message in messages:
                id_ = stored_message.id
                self._send_message_event(message=stored_message, id_=id_)

    def get_connected_model_name(self):
        if self.vertex.incoming_edges:
            source_id = self.vertex.incoming_edges[0].source_id
            _source_vertex = self.graph.get_vertex(source_id)
            _display = _source_vertex.display_name
            data = _source_vertex.data

            # Check for different possible model name keys
            node_template = data.get("node", {}).get("template", {})
            return (
                node_template.get("model_name", {}).get("value")
                or node_template.get("model_id", {}).get("value")
                or node_template.get("model", {}).get("value")
                or _display
            )
        return None

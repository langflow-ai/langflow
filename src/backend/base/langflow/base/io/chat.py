from typing import cast

from langflow.custom import Component
from langflow.memory import store_message
from langflow.schema import Data
from langflow.schema.message import Message


class ChatComponent(Component):
    display_name = "Chat Component"
    description = "Use as base for chat components."

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

    def get_properties_from_source_component(self):
        if self.vertex.incoming_edges:
            source_id = self.vertex.incoming_edges[0].source_id
            _source_vertex = self.graph.get_vertex(source_id)
            component = _source_vertex.custom_component
            source = component.display_name
            icon = component.icon
            possible_attributes = ["model_name", "model_id", "model"]
            for attribute in possible_attributes:
                if hasattr(component, attribute) and getattr(component, attribute):
                    return getattr(component, attribute), icon, source, component._id
            return source, icon, component.display_name, component._id
        return None, None, None, None

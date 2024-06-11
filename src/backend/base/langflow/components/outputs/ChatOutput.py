from typing import Optional

from langflow.base.io.chat import ChatComponent
from langflow.schema.message import Message


class ChatOutput(ChatComponent):
    display_name = "Chat Output"
    description = "Display a chat message in the Playground."
    icon = "ChatOutput"

    def build(
        self,
        sender: Optional[str] = "Machine",
        sender_name: Optional[str] = "AI",
        input_value: Optional[str] = None,
        session_id: Optional[str] = None,
        files: Optional[list[str]] = None,
    ) -> Message:
        return super().build_with_record(
            sender=sender,
            sender_name=sender_name,
            input_value=input_value,
            session_id=session_id,
            files=files,
        )

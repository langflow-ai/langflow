from typing import Optional

from langflow import CustomComponent
from langflow.field_typing import Text


class ChatOutput(CustomComponent):
    display_name = "Chat Output"
    description = "Used to send a message to the chat."

    field_config = {
        "code": {
            "show": True,
        }
    }

    def build_config(self):
        return {
            "message": {"input_types": ["Text"], "display_name": "Message"},
            "sender": {"options": ["Machine", "User"], "display_name": "Sender Type"},
            "sender_name": {"display_name": "Sender Name"},
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
        }

    def build(
        self,
        sender: Optional[str] = "Machine",
        sender_name: Optional[str] = "AI",
        session_id: Optional[str] = None,
        message: Optional[str] = None,
    ) -> Text:
        self.repr_value = message
        if not message:
            message = ""
        return message

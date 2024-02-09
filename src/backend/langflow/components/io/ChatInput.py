from typing import Optional

from langflow import CustomComponent
from langflow.field_typing import Text


class ChatInput(CustomComponent):
    display_name = "Chat Input"
    description = "Used to get user input from the chat."

    def build_config(self):
        return {
            "message": {"input_types": ["Text"], "display_name": "Message"},
            "sender": {"options": ["Machine", "User"], "display_name": "Sender Type"},
            "sender_name": {"display_name": "Sender Name"},
        }

    def build(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "You",
        message: Optional[str] = None,
    ) -> Text:
        self.repr_value = message
        if not message:
            message = ""
        return message

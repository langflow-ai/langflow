from typing import Optional, Text
from langflow import CustomComponent


class ChatInput(CustomComponent):
    display_name = "Chat Input"
    description = "Used to get user input from the chat."

    field_config = {
        "code": {
            "show": False,
        }
    }

    def build(self, message: Optional[str] = "") -> Text:
        self.repr_value = message
        return message

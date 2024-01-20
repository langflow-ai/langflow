from typing import Optional

from langflow import CustomComponent
from langflow.field_typing import Text


class ChatInput(CustomComponent):
    display_name = "Chat Input"
    description = "Used to get user input from the chat."

    field_config = {
        "code": {
            "show": False,
        }
    }

    def build(self, message: Optional[str] = None) -> Text:
        self.repr_value = message
        if not message:
            message = ""
        return message

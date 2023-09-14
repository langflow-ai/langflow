from typing import Optional
from langflow import CustomComponent


class ChatInput(CustomComponent):
    display_name = "Chat Input"

    def build(self, message: Optional[str] = "") -> str:
        return message

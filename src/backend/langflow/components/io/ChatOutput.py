from typing import Optional
from langflow import CustomComponent

from langflow.field_typing import Text


class ChatOutput(CustomComponent):
    display_name = "Chat Output"
    description = "Used to send a message to the chat."

    field_config = {
        "code": {
            "show": False,
        }
    }

    def build_config(self):
        return {"message": {"input_types": ["Text"]}}

    def build(self, is_ai: bool = True, message: Optional[Text] = "") -> Text:
        self.repr_value = message
        return message

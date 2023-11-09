from typing import Optional, Union
from langflow import CustomComponent
from langflow.field_typing import Text, Data


class ChatInput(CustomComponent):
    display_name = "Chat Input"
    description = "Used to get user input from the chat."

    field_config = {
        "code": {
            "show": False,
        }
    }

    def build(self, message: Optional[str] = "") -> Union[Text, Data]:
        self.repr_value = message

        return message

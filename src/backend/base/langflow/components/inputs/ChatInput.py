from typing import Optional, Union

from langflow.base.io.chat import ChatComponent
from langflow.field_typing import Text
from langflow.schema import Record


class ChatInput(ChatComponent):
    display_name = "Chat Input"
    description = "Get chat inputs from the Playground."
    icon = "ChatInput"

    def build_config(self):
        build_config = super().build_config()
        build_config["input_value"] = {
            "input_types": [],
            "display_name": "Message",
            "multiline": True,
        }

        return build_config

    def build(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "User",
        input_value: Optional[str] = None,
        session_id: Optional[str] = None,
        return_record: Optional[bool] = False,
    ) -> Union[Text, Record]:
        return super().build_no_record(
            sender=sender,
            sender_name=sender_name,
            input_value=input_value,
            session_id=session_id,
            return_record=return_record,
        )

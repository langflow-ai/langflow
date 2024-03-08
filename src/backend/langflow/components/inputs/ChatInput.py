from typing import Optional, Union

from langflow.base.io.chat import ChatComponent
from langflow.field_typing import Text
from langflow.schema import Record


class ChatInput(ChatComponent):
    display_name = "Chat Input"
    description = "Used to get user input from the chat."
    icon = "ChatInput"

    def build(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "User",
        input_value: Optional[str] = None,
        session_id: Optional[str] = None,
        return_record: Optional[bool] = False,
    ) -> Union[Text, Record]:
        return super().build(
            sender=sender,
            sender_name=sender_name,
            input_value=input_value,
            session_id=session_id,
            return_record=return_record,
        )

from typing import Optional, Union

from langflow.base.io.chat import ChatComponent
from langflow.field_typing import Text
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
        return_message: Optional[bool] = False,
    ) -> Union[Message, Text]:
        return super().build_with_record(
            sender=sender,
            sender_name=sender_name,
            input_value=input_value,
            session_id=session_id,
            files=files,
            return_message=return_message,
        )

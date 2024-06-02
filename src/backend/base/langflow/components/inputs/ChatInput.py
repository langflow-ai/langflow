from langflow.base.io.chat import ChatComponent
from langflow.field_typing import Text
from langflow.schema import Record
from langflow.template import Input, Output


class ChatInput(ChatComponent):
    display_name = "Chat Input"
    description = "Get chat inputs from the Playground."
    icon = "ChatInput"

    inputs = [
        Input(name="input_value", type=str, display_name="Message", multiline=True, input_types=[]),
        Input(name="sender", type=str, display_name="Sender Type", options=["Machine", "User"]),
        Input(name="sender_name", type=str, display_name="Sender Name"),
        Input(name="session_id", type=str, display_name="Session ID"),
    ]
    outputs = [
        Output(name="Message", method="text_response"),
        Output(name="Record", method="record_response"),
    ]

    def text_response(self) -> Text:
        result = self.message
        if self.session_id and isinstance(result, (Record, str)):
            self.store_message(result, self.session_id, self.sender, self.sender_name)
        return result

    def record_response(self) -> Record:
        record = Record(
            data={
                "message": self.message,
                "sender": self.sender,
                "sender_name": self.sender_name,
                "session_id": self.session_id,
            }
        )
        if self.session_id and isinstance(record, (Record, str)):
            self.store_message(record, self.session_id, self.sender, self.sender_name)
        return record

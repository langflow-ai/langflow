from langflow.base.io.chat import ChatComponent
from langflow.field_typing import Text
from langflow.schema import Record
from langflow.template import Input, Output


class ChatOutput(ChatComponent):
    display_name = "Chat Output"
    description = "Display a chat message in the Playground."
    icon = "ChatOutput"

    inputs = [
        Input(name="input_value", type=str, display_name="Message", multiline=True),
        Input(name="sender", type=str, display_name="Sender Type", options=["Machine", "AI"]),
        Input(name="sender_name", type=str, display_name="Sender Name"),
        Input(name="session_id", type=str, display_name="Session ID"),
        Input(name="record_template", type=str, display_name="Record Template", default="{text}"),
    ]
    outputs = [
        Output(name="Message", method="text_response"),
        Output(name="Record", method="record_response"),
    ]

    def text_response(self) -> Text:
        result = self.input_value
        if self.session_id and isinstance(result, (Record, str)):
            self.store_message(result, self.session_id, self.sender, self.sender_name)
        return result

    def record_response(self) -> Record:
        record = Record(
            data={
                "message": self.input_value,
                "sender": self.sender,
                "sender_name": self.sender_name,
                "session_id": self.session_id,
                "template": self.record_template or "",
            }
        )
        if self.session_id and isinstance(record, (Record, str)):
            self.store_message(record, self.session_id, self.sender, self.sender_name)
        return record

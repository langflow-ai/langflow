from typing import Optional, Union

from langflow import CustomComponent
from langflow.field_typing import Text
from langflow.schema import Record


class ChatInput(CustomComponent):
    display_name = "Chat Input"
    description = "Used to get user input from the chat."

    def build_config(self):
        return {
            "message": {
                "input_types": ["Text"],
                "display_name": "Message",
                "multiline": True,
            },
            "sender": {
                "options": ["Machine", "User"],
                "display_name": "Sender Type",
            },
            "sender_name": {"display_name": "Sender Name"},
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
            },
            "as_record": {
                "display_name": "As Record",
                "info": "If true, the message will be returned as a Record.",
            },
        }

    def build(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "User",
        message: Optional[str] = None,
        as_record: Optional[bool] = False,
        session_id: Optional[str] = None,
    ) -> Union[Text, Record]:
        self.status = message
        if as_record:
            if isinstance(message, Record):
                # Update the data of the record
                message.data["sender"] = sender
                message.data["sender_name"] = sender_name
                message.data["session_id"] = session_id
                return message
            return Record(
                text=message,
                data={
                    "sender": sender,
                    "sender_name": sender_name,
                    "session_id": session_id,
                },
            )
        if not message:
            message = ""
        self.status = message
        return message

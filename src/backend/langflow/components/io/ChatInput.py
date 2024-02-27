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
            "return_record": {
                "display_name": "Return Record",
                "info": "Return the message as a record containing the sender, sender_name, and session_id.",
            },
        }

    def build(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "User",
        message: Optional[str] = None,
        session_id: Optional[str] = None,
        return_record: Optional[bool] = False,
    ) -> Union[Text, Record]:
        if return_record:
            if isinstance(message, Record):
                # Update the data of the record
                message.data["sender"] = sender
                message.data["sender_name"] = sender_name
                message.data["session_id"] = session_id
            else:
                message = Record(
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

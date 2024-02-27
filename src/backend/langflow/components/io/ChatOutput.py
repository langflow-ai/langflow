from typing import Optional, Union

from langflow import CustomComponent
from langflow.field_typing import Text
from langflow.schema import Record


class ChatOutput(CustomComponent):
    display_name = "Chat Output"
    description = "Used to send a message to the chat."

    field_config = {
        "code": {
            "show": True,
        }
    }

    def build_config(self):
        return {
            "input_value": {"input_types": ["Text"], "display_name": "Message"},
            "sender": {
                "options": ["Machine", "User"],
                "display_name": "Sender Type",
            },
            "sender_name": {"display_name": "Sender Name"},
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
            "return_record": {
                "display_name": "Return Record",
                "info": "Return the message as a record containing the sender, sender_name, and session_id.",
            },
        }

    def build(
        self,
        sender: Optional[str] = "Machine",
        sender_name: Optional[str] = "AI",
        session_id: Optional[str] = None,
        input_value: Optional[str] = None,
        return_record: Optional[bool] = False,
    ) -> Union[Text, Record]:
        if return_record:
            if isinstance(input_value, Record):
                # Update the data of the record
                input_value.data["sender"] = sender
                input_value.data["sender_name"] = sender_name
                input_value.data["session_id"] = session_id
            else:
                input_value = Record(
                    text=input_value,
                    data={
                        "sender": sender,
                        "sender_name": sender_name,
                        "session_id": session_id,
                    },
                )
        if not input_value:
            input_value = ""
        self.status = input_value
        return input_value

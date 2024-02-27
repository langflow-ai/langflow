import warnings
from typing import Optional, Union

from langflow import CustomComponent
from langflow.field_typing import Text
from langflow.memory import add_messages
from langflow.schema import Record


class ChatComponent(CustomComponent):
    display_name = "Chat Component"
    description = "Use as base for chat components."

    def build_config(self):
        return {
            "input_value": {
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
                "info": "If provided, the message will be stored in the memory.",
            },
            "return_record": {
                "display_name": "Return Record",
                "info": "Return the message as a record containing the sender, sender_name, and session_id.",
            },
        }

    def store_message(
        self,
        message: Union[Text, Record],
        session_id: Optional[str] = None,
        sender: Optional[str] = None,
        sender_name: Optional[str] = None,
    ) -> list[Record]:
        if not message:
            warnings.warn("No message provided.")
            return []

        if not session_id or not sender or not sender_name:
            raise ValueError(
                "All of session_id, sender, and sender_name must be provided."
            )

        if not record:
            record = []
            if not session_id or not sender or not sender_name:
                raise ValueError
            for text in text:
                record = Record(
                    text=text,
                    data={
                        "session_id": session_id,
                        "sender": sender,
                        "sender_name": sender_name,
                    },
                )
                record.append(record)
        elif isinstance(record, Record):
            record = [record]

        self.status = record
        record = add_messages(record)
        return record

    def build(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "User",
        input_value: Optional[str] = None,
        session_id: Optional[str] = None,
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
        if session_id:
            self.store_message(input_value, session_id, sender, sender_name)
        return input_value

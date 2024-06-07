from typing import Optional, Union

from langflow.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES
from langflow.custom import CustomComponent
from langflow.field_typing import Text
from langflow.helpers.record import records_to_text
from langflow.memory import store_message
from langflow.schema import Record
from langflow.schema.message import Message


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
                "advanced": True,
            },
            "sender_name": {"display_name": "Sender Name"},
            "session_id": {
                "display_name": "Session ID",
                "info": "If provided, the message will be stored in the memory.",
                "advanced": True,
            },
            "return_record": {
                "display_name": "Return Record",
                "info": "Return the message as a record containing the sender, sender_name, and session_id.",
                "advanced": True,
            },
            "record_template": {
                "display_name": "Record Template",
                "multiline": True,
                "info": "In case of Message being a Record, this template will be used to convert it to text.",
                "advanced": True,
            },
            "files": {
                "field_type": "file",
                "display_name": "Files",
                "file_types": TEXT_FILE_TYPES + IMG_FILE_TYPES,
                "info": "Files to be sent with the message.",
                "advanced": True,
            },
        }

    def store_message(
        self,
        message: Message,
    ) -> list[Record]:
        messages = store_message(
            message,
            flow_id=self.graph.flow_id,
        )

        self.status = messages
        return messages

    def build_with_record(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "User",
        input_value: Optional[Union[str, Record, Message]] = None,
        files: Optional[list[str]] = None,
        session_id: Optional[str] = None,
    ) -> Message:
        message: Message | None = None

        if isinstance(input_value, Record):
            # Update the data of the record
            message = Message.from_record(input_value)
        else:
            message = Message(
                text=input_value, sender=sender, sender_name=sender_name, files=files, session_id=session_id
            )
        self.status = message
        if session_id and isinstance(message, Message):
            self.store_message(message, session_id, sender, sender_name)
        return message

    def build_no_record(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "User",
        input_value: Optional[str] = None,
        files: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        return_record: Optional[bool] = False,
        record_template: str = "Text: {text}\nData: {data}",
    ) -> Union[Text, Record]:
        input_value_record: Optional[Record] = None
        if files and not return_record:
            raise ValueError("Files can only be provided when Return Record is enabled.")
        if return_record:
            if isinstance(input_value, Record):
                # Update the data of the record
                input_value.data["sender"] = sender
                input_value.data["sender_name"] = sender_name
                input_value.data["session_id"] = session_id
                input_value.data["files"] = files
            else:
                input_value_record = Record(
                    text=input_value,
                    data={
                        "sender": sender,
                        "sender_name": sender_name,
                        "session_id": session_id,
                        "files": files,
                    },
                )
        elif isinstance(input_value, Record):
            input_value = records_to_text(template=record_template, records=input_value)
        if not input_value:
            input_value = ""
        if return_record and input_value_record:
            result: Union[Text, Record] = input_value_record
        else:
            result = input_value
        self.status = result
        if session_id and isinstance(result, (Record, str)):
            self.store_message(result, session_id, sender, sender_name)
        return result

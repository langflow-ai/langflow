from typing import Optional, Union

from langflow.field_typing import Text
from langflow.helpers.record import records_to_text
from langflow.interface.custom.custom_component import CustomComponent
from langflow.memory import store_message
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
        }

    def store_message(
        self,
        message: Union[str, Text, Record],
        session_id: Optional[str] = None,
        sender: Optional[str] = None,
        sender_name: Optional[str] = None,
    ) -> list[Record]:

        records = store_message(
            message,
            session_id=session_id,
            sender=sender,
            sender_name=sender_name,
        )

        self.status = records
        return records

    def build_with_record(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "User",
        input_value: Optional[Union[str, Record]] = None,
        session_id: Optional[str] = None,
        return_record: Optional[bool] = False,
        record_template: str = "Text: {text}\nData: {data}",
    ) -> Union[Text, Record]:
        input_value_record: Optional[Record] = None
        if return_record:
            if isinstance(input_value, Record):
                # Update the data of the record
                input_value.data["sender"] = sender
                input_value.data["sender_name"] = sender_name
                input_value.data["session_id"] = session_id
            else:
                input_value_record = Record(
                    text=input_value,
                    data={
                        "sender": sender,
                        "sender_name": sender_name,
                        "session_id": session_id,
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

    def build_no_record(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "User",
        input_value: Optional[str] = None,
        session_id: Optional[str] = None,
        return_record: Optional[bool] = False,
        record_template: str = "Text: {text}\nData: {data}",
    ) -> Union[Text, Record]:
        input_value_record: Optional[Record] = None
        if return_record:
            if isinstance(input_value, Record):
                # Update the data of the record
                input_value.data["sender"] = sender
                input_value.data["sender_name"] = sender_name
                input_value.data["session_id"] = session_id
            else:
                input_value_record = Record(
                    text=input_value,
                    data={
                        "sender": sender,
                        "sender_name": sender_name,
                        "session_id": session_id,
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

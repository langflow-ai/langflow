import warnings
from typing import Optional, Union

from langchain_community.chat_message_histories import AstraDBChatMessageHistory

from langflow.field_typing import Text
from langflow.helpers.record import records_to_text
from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record


class AstraDBChatComponent(CustomComponent):
    display_name = "Astra DB Chat Component"
    description = "Use as base for Astra DB chat components."

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
        astra_messages: AstraDBChatMessageHistory,
        message: Union[str, Text, Record],
        session_id: Optional[str] = None,
        sender: Optional[str] = None,
        sender_name: Optional[str] = None,
    ) -> list[Record]:
        if not message:
            warnings.warn("No message provided.")
            return []

        if not session_id or not sender or not sender_name:
            raise ValueError("All of session_id, sender, and sender_name must be provided.")
        if isinstance(message, Record):
            record = message
            record.data.update(
                {
                    "session_id": session_id,
                    "sender": sender,
                    "sender_name": sender_name,
                }
            )
        else:
            record = Record(
                data={
                    "text": message,
                    "session_id": session_id,
                    "sender": sender,
                    "sender_name": sender_name,
                },
            )

        records = astra_messages.add_user_message(record.text)

        return records[0]

    def build(
        self,
        api_endpoint: Optional[str] = None,
        token: Optional[str] = None,
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

        # Initialize the AstraDBChatMessageHistory class
        astra_messages = AstraDBChatMessageHistory(
            session_id=session_id,
            api_endpoint=api_endpoint,
            token=token,
        )

        if session_id and isinstance(result, (Record, str)):
            self.store_message(astra_messages, result, session_id, sender, sender_name)

        return result

from typing import Optional, Union

from langflow.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES
from langflow.custom import Component
from langflow.memory import store_message
from langflow.schema import Data
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_USER, MESSAGE_SENDER_AI


class ChatComponent(Component):
    display_name = "Chat Component"
    description = "Use as base for chat components."

    def build_config(self):
        return {
            "input_value": {
                "input_types": ["Text"],
                "display_name": "Text",
                "multiline": True,
            },
            "sender": {
                "options": [MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],
                "display_name": "Sender Type",
                "advanced": True,
            },
            "sender_name": {"display_name": "Sender Name", "advanced": True},
            "session_id": {
                "display_name": "Session ID",
                "info": "If provided, the message will be stored in the memory.",
                "advanced": True,
            },
            "return_message": {
                "display_name": "Return Message",
                "info": "Return the message as a Message containing the sender, sender_name, and session_id.",
                "advanced": True,
            },
            "data_template": {
                "display_name": "Data Template",
                "multiline": True,
                "info": "In case of Message being a Data, this template will be used to convert it to text.",
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

    # Keep this method for backward compatibility
    def store_message(
        self,
        message: Message,
    ) -> list[Message]:
        messages = store_message(
            message,
            flow_id=self.graph.flow_id,
        )

        self.status = messages
        return messages

    def build_with_data(
        self,
        sender: Optional[str] = "User",
        sender_name: Optional[str] = "User",
        input_value: Optional[Union[str, Data, Message]] = None,
        files: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        return_message: Optional[bool] = False,
    ) -> Message:
        message: Message | None = None

        if isinstance(input_value, Data):
            # Update the data of the record
            message = Message.from_data(input_value)
        else:
            message = Message(
                text=input_value, sender=sender, sender_name=sender_name, files=files, session_id=session_id
            )
        if not return_message:
            message_text = message.text
        else:
            message_text = message  # type: ignore

        self.status = message_text
        if session_id and isinstance(message, Message) and isinstance(message.text, str):
            messages = store_message(
                message,
                flow_id=self.graph.flow_id,
            )
            self.status = messages
        return message_text  # type: ignore

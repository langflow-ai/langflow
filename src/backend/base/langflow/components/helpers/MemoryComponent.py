from typing import Optional

from langflow.base.memory.memory import BaseMemoryComponent
from langflow.field_typing import Text
from langflow.helpers.record import records_to_text
from langflow.memory import get_messages
from langflow.schema.schema import Record


class MemoryComponent(BaseMemoryComponent):
    display_name = "Chat Memory"
    description = "Retrieves stored chat messages given a specific Session ID."
    beta: bool = True
    icon = "history"

    def build_config(self):
        return {
            "sender": {
                "options": ["Machine", "User", "Machine and User"],
                "display_name": "Sender Type",
            },
            "sender_name": {"display_name": "Sender Name", "advanced": True},
            "n_messages": {
                "display_name": "Number of Messages",
                "info": "Number of messages to retrieve.",
            },
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
            "order": {
                "options": ["Ascending", "Descending"],
                "display_name": "Order",
                "info": "Order of the messages.",
                "advanced": True,
            },
            "record_template": {
                "display_name": "Record Template",
                "multiline": True,
                "info": "Template to convert Record to Text. If left empty, it will be dynamically set to the Record's text key.",
                "advanced": True,
            },
        }

    def get_messages(self, **kwargs) -> list[Record]:
        # Validate kwargs by checking if it contains the correct keys
        if "sender" not in kwargs:
            kwargs["sender"] = None
        if "sender_name" not in kwargs:
            kwargs["sender_name"] = None
        if "session_id" not in kwargs:
            kwargs["session_id"] = None
        if "limit" not in kwargs:
            kwargs["limit"] = 5
        if "order" not in kwargs:
            kwargs["order"] = "Descending"

        kwargs["order"] = "DESC" if kwargs["order"] == "Descending" else "ASC"
        if kwargs["sender"] == "Machine and User":
            kwargs["sender"] = None
        return get_messages(**kwargs)

    def build(
        self,
        sender: Optional[str] = "Machine and User",
        sender_name: Optional[str] = None,
        session_id: Optional[str] = None,
        n_messages: int = 5,
        order: Optional[str] = "Descending",
        record_template: Optional[str] = "{sender_name}: {text}",
    ) -> Text:
        messages = self.get_messages(
            sender=sender,
            sender_name=sender_name,
            session_id=session_id,
            limit=n_messages,
            order=order,
        )
        messages_str = records_to_text(template=record_template or "", records=messages)
        self.status = messages_str
        return messages_str

from typing import Optional

from langflow.field_typing import Text
from langflow.helpers.record import records_to_text
from langflow.interface.custom.custom_component import CustomComponent
from langflow.memory import get_messages


class MemoryComponent(CustomComponent):
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

    def build(
        self,
        sender: Optional[str] = "Machine and User",
        sender_name: Optional[str] = None,
        session_id: Optional[str] = None,
        n_messages: int = 5,
        order: Optional[str] = "Descending",
        record_template: Optional[str] = "{sender_name}: {text}",
    ) -> Text:
        order = "DESC" if order == "Descending" else "ASC"
        if sender == "Machine and User":
            sender = None
        messages = get_messages(
            sender=sender,
            sender_name=sender_name,
            session_id=session_id,
            limit=n_messages,
            order=order,
        )
        messages_str = records_to_text(template=record_template, records=messages)
        self.status = messages_str
        return messages_str

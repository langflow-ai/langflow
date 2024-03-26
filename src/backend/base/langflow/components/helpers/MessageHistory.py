from typing import List, Optional

from langflow.interface.custom.custom_component import CustomComponent
from langflow.memory import get_messages
from langflow.schema import Record


class MessageHistoryComponent(CustomComponent):
    display_name = "Message History"
    description = "Used to retrieve stored messages."
    beta: bool = True

    def build_config(self):
        return {
            "sender": {
                "options": ["Machine", "User", "Machine and User"],
                "display_name": "Sender Type",
            },
            "sender_name": {"display_name": "Sender Name"},
            "n_messages": {
                "display_name": "Number of Messages",
                "info": "Number of messages to retrieve.",
            },
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
        }

    def build(
        self,
        sender: Optional[str] = None,
        sender_name: Optional[str] = None,
        session_id: Optional[str] = None,
        n_messages: int = 5,
    ) -> List[Record]:
        if sender == "Machine and User":
            sender = None
        messages = get_messages(
            sender=sender,
            sender_name=sender_name,
            session_id=session_id,
            limit=n_messages,
        )
        self.status = messages
        return messages

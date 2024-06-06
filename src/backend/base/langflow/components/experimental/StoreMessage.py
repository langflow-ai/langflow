from typing import List, Optional

from langflow.custom import CustomComponent
from langflow.memory import get_messages, store_message
from langflow.schema import Record


class StoreMessageComponent(CustomComponent):
    display_name = "Store Message"
    description = "Stores a chat message given a Session ID."
    beta: bool = True

    def build_config(self):
        return {
            "sender": {
                "options": ["Machine", "User"],
                "display_name": "Sender Type",
            },
            "sender_name": {"display_name": "Sender Name"},
            "message": {"display_name": "Message"},
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
        }

    def build(
        self,
        sender: str = "User",
        sender_name: Optional[str] = None,
        session_id: Optional[str] = None,
        message: str = "",
    ) -> List[Record]:
        store_message(
            sender=sender,
            sender_name=sender_name,
            session_id=session_id,
            message=message,
        )

        self.status = get_messages(session_id=session_id)
        return get_messages(session_id=session_id)

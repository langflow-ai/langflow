from typing import List, Optional

from langflow import CustomComponent
from langflow.memory import get_messages
from langflow.schema import Record


class MessageHistoryComponent(CustomComponent):
    display_name = "Message History"
    description = "Used to retrieve stored messages."

    def build_config(self):
        return {
            "sender": {
                "options": ["Machine", "User"],
                "display_name": "Sender Type",
            },
            "sender_name": {"display_name": "Sender Name"},
            "file_path": {
                "display_name": "File Path",
                "info": "Path of the local JSON file to store the messages. It should be a unique path for each chat history.",
            },
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
        messages = get_messages(
            sender=sender,
            sender_name=sender_name,
            session_id=session_id,
            limit=n_messages,
        )
        self.status = messages
        return messages

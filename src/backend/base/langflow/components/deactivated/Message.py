from typing import Optional

from langflow.custom import CustomComponent
from langflow.schema.message import Message


class MessageComponent(CustomComponent):
    display_name = "Message"
    description = "Creates a Message object given a Session ID."

    def build_config(self):
        return {
            "sender": {
                "options": ["Machine", "User"],
                "display_name": "Sender Type",
            },
            "sender_name": {"display_name": "Sender Name"},
            "text": {"display_name": "Text"},
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
        text: str = "",
    ) -> Message:
        message = Message(
            text=text, sender=sender, sender_name=sender_name, flow_id=self.graph.flow_id, session_id=session_id
        )

        self.status = message
        return message

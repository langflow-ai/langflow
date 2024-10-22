from langflow.custom import CustomComponent
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER


class MessageComponent(CustomComponent):
    display_name = "Message"
    description = "Creates a Message object given a Session ID."
    name = "Message"

    def build_config(self):
        return {
            "sender": {
                "options": [MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],
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
        sender: str = MESSAGE_SENDER_USER,
        sender_name: str | None = None,
        session_id: str | None = None,
        text: str = "",
    ) -> Message:
        message = Message(
            text=text, sender=sender, sender_name=sender_name, flow_id=self.graph.flow_id, session_id=session_id
        )

        self.status = message
        return message

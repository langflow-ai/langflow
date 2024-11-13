from langflow.custom import CustomComponent
from langflow.memory import get_messages, store_message
from langflow.schema.message import Message


class StoreMessageComponent(CustomComponent):
    display_name = "Store Message"
    description = "Stores a chat message."
    name = "StoreMessage"

    def build_config(self):
        return {
            "message": {"display_name": "Message"},
        }

    def build(
        self,
        message: Message,
    ) -> Message:
        flow_id = self.graph.flow_id if hasattr(self, "graph") else None
        store_message(message, flow_id=flow_id)
        self.status = get_messages()

        return message

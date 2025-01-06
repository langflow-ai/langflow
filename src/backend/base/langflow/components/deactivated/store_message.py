from langflow.custom import CustomComponent
from langflow.memory import aget_messages, astore_message
from langflow.schema.message import Message


class StoreMessageComponent(CustomComponent):
    display_name = "Store Message"
    description = "Stores a chat message."
    name = "StoreMessage"

    def build_config(self):
        return {
            "message": {"display_name": "Message"},
        }

    async def build(
        self,
        message: Message,
    ) -> Message:
        flow_id = self.graph.flow_id if hasattr(self, "graph") else None
        await astore_message(message, flow_id=flow_id)
        self.status = await aget_messages()

        return message

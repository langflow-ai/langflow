from langflow.custom.custom_component.custom_component import CustomComponent
from langflow.schema.data import Data
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER


class BaseMemoryComponent(CustomComponent):
    display_name = "Chat Memory"
    description = "Retrieves stored chat messages given a specific Session ID."
    beta: bool = True
    icon = "history"

    def build_config(self):
        return {
            "sender": {
                "options": [MESSAGE_SENDER_AI, MESSAGE_SENDER_USER, "Machine and User"],
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
                "input_types": ["Message"],
            },
            "order": {
                "options": ["Ascending", "Descending"],
                "display_name": "Order",
                "info": "Order of the messages.",
                "advanced": True,
            },
            "data_template": {
                "display_name": "Data Template",
                "multiline": True,
                "info": "Template to convert Data to Text. "
                "If left empty, it will be dynamically set to the Data's text key.",
                "advanced": True,
            },
        }

    def get_messages(self, **kwargs) -> list[Data]:
        raise NotImplementedError

    def add_message(
        self, sender: str, sender_name: str, text: str, session_id: str, metadata: dict | None = None, **kwargs
    ) -> None:
        raise NotImplementedError

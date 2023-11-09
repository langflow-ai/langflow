from typing import Optional, Union
from langflow import CustomComponent

from langflow.field_typing import Text, Data
import pandas as pd
from platformdirs import user_cache_dir
from datetime import datetime


class ChatOutput(CustomComponent):
    display_name = "Chat Output"
    description = "Used to send a message to the chat."

    field_config = {
        "code": {
            "show": True,
        }
    }

    def build_config(self):
        return {
            "message": {"input_types": ["Text"]},
            "sender": {"options": ["Machine", "User"], "display_name": "Sender Type"},
            "sender_name": {"display_name": "Sender Name"},
        }

    def build(
        self,
        sender: Optional[str] = "Machine",
        sender_name: Optional[str] = "AI",
        message: Optional[Text] = "",
        file_path: str = "chat_history.json",
    ) -> Union[Text, Data]:
        self.repr_value = message
        # Load the chat history df
        chat_history_df = pd.read_json(user_cache_dir("langflow") + "/" + file_path)
        # Add the message to the df
        chat_history_df = chat_history_df.append(
            {
                "sender": sender,
                "sender_name": sender_name,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
            },
            ignore_index=True,
        )
        # Save the df
        chat_history_df.to_json(user_cache_dir("langflow") + "/" + file_path)
        return message

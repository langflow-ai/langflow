from typing import List, Optional
from langflow import CustomComponent
from langchain.schema import Document
from langflow.services.getters import get_monitor_service


class MessageHistoryComponent(CustomComponent):
    display_name = "Message History"
    description = "Used to retrieve stored messages."

    def build_config(self):
        return {
            "sender": {"options": ["Machine", "User"], "display_name": "Sender Type"},
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
    ) -> List[Document]:
        # Load the chat history df
        monitor_service = get_monitor_service()
        chat_history_df = monitor_service.to_df("messages")

        # Filter the df
        if session_id:
            chat_history_df = chat_history_df[
                chat_history_df["session_id"] == session_id
            ]
        if sender:
            chat_history_df = chat_history_df[chat_history_df["sender_type"] == sender]
        if sender_name:
            chat_history_df = chat_history_df[
                chat_history_df["sender_name"] == sender_name
            ]
        # Sort the df
        chat_history_df = chat_history_df.sort_values(by="timestamp")
        # Get the last n messages
        if n_messages:
            chat_history_df = chat_history_df.tail(n_messages)
        # Create a list of messages
        messages = []
        for _, row in chat_history_df.iterrows():
            messages.append(
                Document(page_content=f"{row['sender_name']}: {row['message']}")
            )
        # Return the list of messages
        return messages

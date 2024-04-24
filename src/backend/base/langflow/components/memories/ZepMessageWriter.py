from langchain_community.chat_message_histories.zep import ZepChatMessageHistory

from langflow.base.memory.memory import BaseMemoryComponent
from langflow.field_typing import Text
from langflow.schema.schema import Record


class ZepMessageReaderComponent(BaseMemoryComponent):
    display_name = "Zep Message Reader"
    description = "Retrieves stored chat messages from Zep."

    def build_config(self):
        return {
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
            "url": {
                "display_name": "Zep URL",
                "info": "URL of the Zep instance.",
                "input_types": ["Text"],
            },
            "api_key": {
                "display_name": "Zep API Key",
                "info": "API Key for the Zep instance.",
                "password": True,
            },
            "query": {
                "display_name": "Query",
                "info": "Query to search for in the chat history.",
            },
            "metadata": {
                "display_name": "Metadata",
                "info": "Optional metadata to attach to the message.",
                "advanced": True,
            },
            "search_scope": {
                "options": ["Messages", "Summary"],
                "display_name": "Search Scope",
                "info": "Scope of the search.",
                "advanced": True,
            },
            "search_type": {
                "options": ["Similarity", "MMR"],
                "display_name": "Search Type",
                "info": "Type of search.",
                "advanced": True,
            },
            "limit": {
                "display_name": "Limit",
                "info": "Limit of search results.",
                "advanced": True,
            },
        }

    def add_message(
        self, sender: Text, sender_name: Text, message: Text, session_id: Text, metadata: dict | None = None, **kwargs
    ):
        """
        Adds a message to the ZepChatMessageHistory memory.

        Args:
            sender (Text): The type of the message sender. Valid values are "Machine" or "User".
            sender_name (Text): The name of the message sender.
            message (Text): The content of the message.
            session_id (Text): The session ID associated with the message.
            metadata (dict | None, optional): Additional metadata for the message. Defaults to None.
            **kwargs: Additional keyword arguments.

        Raises:
            ValueError: If the ZepChatMessageHistory instance is not provided.

        """
        memory: ZepChatMessageHistory | None = kwargs.pop("memory", None)
        if memory is None:
            raise ValueError("ZepChatMessageHistory instance is required.")
        if metadata is None:
            metadata = {}
        metadata["sender_name"] = sender_name
        metadata.update(kwargs)
        if sender == "Machine":
            memory.add_ai_message(message, metadata=metadata)
        elif sender == "User":
            memory.add_user_message(message, metadata=metadata)
        else:
            raise ValueError(f"Invalid sender type: {sender}")

    def build(
        self,
        input_value: Record,
        session_id: Text,
        url: Text,
        api_key: Text,
    ):
        memory = ZepChatMessageHistory(session_id, url, api_key)
        self.add_message(**input_value.data, memory=memory)
        self.status = f"Added message to Zep memory for session {session_id}"
        return input_value

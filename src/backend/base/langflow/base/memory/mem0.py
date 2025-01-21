from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict
from loguru import logger
from mem0 import Memory, MemoryClient
from mem0.client.main import APIError

ROLE_MAP = {
    "human": "user",
    "ai": "assistant",
}


class Mem0LCMemory(BaseChatMessageHistory):
    """Chat message history that uses Mem0 as a backend.

    Args:
        user_id: The ID of the user whose messages to store
        api_key: Optional Mem0 API key for cloud version
        config: Optional configuration for local Mem0 instance
    """

    def __init__(
        self,
        user_id: str,
        api_key: str | None = None,
        config: dict | None = None,
    ):
        """Initialize by creating a new Mem0 client."""
        self.user_id = user_id

        try:
            if api_key:
                self.client = MemoryClient(api_key=api_key)
            else:
                self.client = Memory.from_config(config_dict=config) if config else Memory()
        except (ImportError, ValueError) as e:
            msg = (
                "Mem0 is not properly installed or invalid configuration."
                " Please install it with 'pip install -U mem0ai'"
            )
            raise ImportError(msg) from e

    @property
    def messages(self) -> list[BaseMessage]:
        """Retrieve the messages from Mem0.

        Returns:
            list[BaseMessage]: List of messages retrieved from Mem0 formatted as markdown.
            Each memory is converted to a markdown bullet point.

        Raises:
            APIError: If there is an error retrieving messages from the Mem0 API.
        """
        try:
            memories = self.client.get_all(user_id=self.user_id)
            if isinstance(memories, dict) and "results" in memories:
                # Handle cloud API response format
                memories = memories["results"]

            # Convert memories to markdown bullet points using list comprehension
            bullet_points = [f"- {mem['memory']}" for mem in memories if isinstance(mem, dict) and "memory" in mem]

            if not bullet_points:
                return []

            # Join bullet points with newlines to create markdown list
            content = "\n".join(bullet_points)
            message_dict = {
                "type": "ai",
                "data": {
                    "content": content,
                },
            }
            return messages_from_dict([message_dict])

        except APIError as e:
            logger.error(f"Error retrieving messages from Mem0: {e}")
            raise

    def add_message(self, message: BaseMessage) -> None:
        """Append the message to Mem0 storage."""
        try:
            message_dict = message_to_dict(message)
            if "data" in message_dict:
                data_dict = message_dict.pop("data")
                message_dict["content"] = data_dict["content"]
            message_dict["role"] = message_dict.pop("type")
            message_dict["role"] = ROLE_MAP.get(message_dict["role"], message_dict["role"])

            self.client.add([message_dict], user_id=self.user_id)
        except APIError as e:
            logger.error(f"Error adding message to Mem0: {e}")
            raise

    def clear(self) -> None:
        """Clear all messages for the user from Mem0."""
        try:
            self.client.delete_all(user_id=self.user_id)
        except APIError as e:
            logger.error(f"Error clearing messages from Mem0: {e}")
            raise

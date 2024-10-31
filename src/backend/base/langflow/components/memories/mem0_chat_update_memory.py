import logging
import os

from mem0 import Memory, MemoryClient

from langflow.base.memory.model import LCChatMemoryComponent
from langflow.inputs import (
    HandleInput,
    MessageTextInput,
    SecretStrInput,
    StrInput,
)
from langflow.io import Output

logger = logging.getLogger(__name__)


class Mem0MemoryComponentUpdateMessage(LCChatMemoryComponent):
    display_name = "Mem0 Chat Memory Update"
    description = "Updates a message in Mem0 memory storage."
    name = "mem0_chat_memory_update"
    icon: str = "Mem0"
    inputs = [
        MessageTextInput(
            name="new_message_content",
            display_name="New Message Content",
            info="The updated content to store in Mem0 memory.",
        ),
        StrInput(
            name="memory_id",
            display_name="Memory ID",
            required=True,
            info="Unique identifier of the memory entry to update.",
        ),
        HandleInput(
            name="existing_memory",
            display_name="Existing Memory Instance",
            input_types=["Memory"],
            info="Existing Mem0 memory instance.",
            required=True,
        ),
        SecretStrInput(
            name="mem0_api_key",
            display_name="Mem0 API Key",
            info="API key for Mem0 platform. Leave empty to use the local version.",
        ),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            required=False,
            info="API key for OpenAI. Required if using OpenAI embeddings without a provided configuration.",
        ),
    ]

    outputs = [
        Output(name="memory", display_name="Mem0 Memory", method="update_data"),
    ]

    def build_mem0(self) -> Memory:
        """Initializes a Mem0 memory instance based on provided API keys."""
        if self.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.openai_api_key
        try:
            return Memory() if not self.mem0_api_key else MemoryClient(api_key=self.mem0_api_key)
        except ImportError as e:
            msg = "Mem0 is not properly installed. Please install it with 'pip install -U mem0ai'."
            raise ImportError(msg) from e

    def update_data(self) -> Memory:
        """Updates a message in Mem0 memory and returns the updated memory instance."""
        memory = self.existing_memory if self.existing_memory else self.build_mem0()

        if not self.new_message_content or not self.memory_id:
            logger.warning("Missing 'new_message_content' or 'memory_id'; cannot update data.")
            return memory

        try:
            memory.update(memory_id=self.memory_id, data=self.new_message_content)
        except Exception:
            logger.exception("Failed to update memory.")
            raise

        return memory

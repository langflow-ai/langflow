import logging
import os

from mem0 import Memory, MemoryClient

from langflow.base.memory.model import LCChatMemoryComponent
from langflow.inputs import (
    HandleInput,
    SecretStrInput,
    StrInput,
)
from langflow.io import Output

logger = logging.getLogger(__name__)


class Mem0MemoryComponentDeleteMemory(LCChatMemoryComponent):
    display_name = "Mem0 Chat Memory Delete"
    description = "Deletes a message from Mem0 memory storage."
    name = "mem0_chat_memory_delete"
    icon: str = "Mem0"
    inputs = [
        StrInput(
            name="memory_id",
            display_name="Memory ID",
            required=True,
            info="Unique identifier of the memory entry to delete.",
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
        Output(name="memory", display_name="Mem0 Memory", method="delete_data"),
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

    def delete_data(self) -> Memory:
        """Deletes a message from Mem0 memory and returns the updated memory instance."""
        memory = self.existing_memory if self.existing_memory else self.build_mem0()

        if not self.memory_id:
            logger.warning("Missing 'memory_id'; cannot delete data.")
            return memory

        try:
            memory.delete(memory_id=self.memory_id)
        except Exception:
            logger.exception("Failed to delete memory.")
            raise

        return memory

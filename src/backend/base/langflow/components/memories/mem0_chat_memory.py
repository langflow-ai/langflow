import logging
import os

from mem0 import Memory, MemoryClient

from langflow.base.memory.model import LCChatMemoryComponent
from langflow.inputs import (
    DictInput,
    HandleInput,
    MessageTextInput,
    NestedDictInput,
    SecretStrInput,
)
from langflow.io import Output
from langflow.schema import Data

logger = logging.getLogger(__name__)


class Mem0MemoryComponent(LCChatMemoryComponent):
    display_name = "Mem0 Chat Memory"
    description = "Retrieves and stores chat messages using Mem0 memory storage."
    name = "mem0_chat_memory"
    icon: str = "Mem0"
    inputs = [
        NestedDictInput(
            name="mem0_config",
            display_name="Mem0 Configuration",
            info="""Configuration dictionary for initializing Mem0 memory instance.
                    Example:
                    {
                        "graph_store": {
                            "provider": "neo4j",
                            "config": {
                                "url": "neo4j+s://your-neo4j-url",
                                "username": "neo4j",
                                "password": "your-password"
                            }
                        },
                        "version": "v1.1"
                    }""",
            input_types=["Data"],
        ),
        MessageTextInput(
            name="ingest_message",
            display_name="Message to Ingest",
            info="The message content to be ingested into Mem0 memory.",
        ),
        HandleInput(
            name="existing_memory",
            display_name="Existing Memory Instance",
            input_types=["Memory"],
            info="Optional existing Mem0 memory instance. If not provided, a new instance will be created.",
        ),
        MessageTextInput(
            name="user_id", display_name="User ID", info="Identifier for the user associated with the messages."
        ),
        MessageTextInput(
            name="search_query", display_name="Search Query", info="Input text for searching related memories in Mem0."
        ),
        SecretStrInput(
            name="mem0_api_key",
            display_name="Mem0 API Key",
            info="API key for Mem0 platform. Leave empty to use the local version.",
        ),
        DictInput(
            name="metadata",
            display_name="Metadata",
            info="Additional metadata to associate with the ingested message.",
            advanced=True,
        ),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            required=False,
            info="API key for OpenAI. Required if using OpenAI Embeddings without a provided configuration.",
        ),
    ]

    outputs = [
        Output(name="memory", display_name="Mem0 Memory", method="ingest_data"),
        Output(
            name="search_results",
            display_name="Search Results",
            method="build_search_results",
        ),
    ]

    def build_mem0(self) -> Memory:
        """Initializes a Mem0 memory instance based on provided configuration and API keys."""
        if self.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.openai_api_key

        try:
            if not self.mem0_api_key:
                return Memory.from_config(config_dict=dict(self.mem0_config)) if self.mem0_config else Memory()
            if self.mem0_config:
                return MemoryClient.from_config(api_key=self.mem0_api_key, config_dict=dict(self.mem0_config))
            return MemoryClient(api_key=self.mem0_api_key)
        except ImportError as e:
            msg = "Mem0 is not properly installed. Please install it with 'pip install -U mem0ai'."
            raise ImportError(msg) from e

    def ingest_data(self) -> Memory:
        """Ingests a new message into Mem0 memory and returns the updated memory instance."""
        mem0_memory = self.existing_memory or self.build_mem0()

        if not self.ingest_message or not self.user_id:
            logger.warning("Missing 'ingest_message' or 'user_id'; cannot ingest data.")
            return mem0_memory

        metadata = self.metadata or {}

        logger.info("Ingesting message for user_id: %s", self.user_id)

        try:
            mem0_memory.add(self.ingest_message, user_id=self.user_id, metadata=metadata)
        except Exception:
            logger.exception("Failed to add message to Mem0 memory.")
            raise

        return mem0_memory

    def build_search_results(self) -> Data:
        """Searches the Mem0 memory for related messages based on the search query and returns the results."""
        mem0_memory = self.ingest_data()
        search_query = self.search_query
        user_id = self.user_id

        logger.info("Search query: %s", search_query)

        try:
            if search_query:
                logger.info("Performing search with query.")
                related_memories = mem0_memory.search(query=search_query, user_id=user_id)
            else:
                logger.info("Retrieving all memories for user_id: %s", user_id)
                related_memories = mem0_memory.get_all(user_id=user_id)
        except Exception:
            logger.exception("Failed to retrieve related memories from Mem0.")
            raise

        logger.info("Related memories retrieved: %s", related_memories)
        return related_memories

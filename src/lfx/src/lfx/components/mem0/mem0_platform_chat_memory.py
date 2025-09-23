from mem0 import MemoryClient

from lfx.base.memory.model import LCChatMemoryComponent
from lfx.inputs.inputs import DictInput, HandleInput, MessageTextInput, NestedDictInput, SecretStrInput
from lfx.io import Output
from lfx.log.logger import logger
from lfx.schema.data import Data


class Mem0PlatformChatMemoryComponent(LCChatMemoryComponent):
    display_name = "Mem0 Platform Chat Memory"
    description = """Retrieves and stores chat messages using Mem0 Platform (hosted) memory storage. 
                Managed solution with enterprise features.
                This component is only available in the Mem0 Platform bundle."""
    name = "mem0_platform_chat_memory"
    icon: str = "Mem0"
    inputs = [
        SecretStrInput(
            name="mem0_api_key",
            display_name="Mem0 API Key",
            info="API key for Mem0 Platform. Required for accessing the hosted Mem0 service.",
            required=True,
        ),
        NestedDictInput(
            name="mem0_config",
            display_name="Mem0 Platform Configuration",
            info="""Optional configuration dictionary for advanced Mem0 Platform settings.
                    Example for Platform with custom settings:
                    {
                        "custom_categories": ["work", "personal", "projects"],
                        "version": "v1.1"
                    }
                    Leave empty to use default platform configuration.""",
            input_types=["Data"],
            advanced=True,
        ),
        MessageTextInput(
            name="ingest_message",
            display_name="Message to Ingest",
            info="The message content to be ingested into Mem0 Platform memory.",
        ),
        HandleInput(
            name="existing_memory",
            display_name="Existing Memory Instance",
            input_types=["Memory"],
            info="Optional existing Mem0 Platform memory client. If not provided, a new client will be created.",
        ),
        MessageTextInput(
            name="user_id", display_name="User ID", info="Identifier for the user associated with the messages."
        ),
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Input text for searching related memories in Mem0 Platform.",
        ),
        DictInput(
            name="metadata",
            display_name="Metadata",
            info="Additional metadata to associate with the ingested message.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="memory", display_name="Mem0 Platform Memory", method="ingest_data"),
        Output(
            name="search_results",
            display_name="Search Results",
            method="build_search_results",
        ),
    ]

    def build_mem0(self) -> MemoryClient:
        """Initializes a Mem0 Platform memory client."""
        if not self.mem0_api_key:
            msg = "Mem0 API key is required for Platform version. Please provide a valid API key."
            raise ValueError(msg)

        try:
            if self.mem0_config:
                logger.info("Initializing Mem0 Platform with API key and custom configuration")
                return MemoryClient.from_config(api_key=self.mem0_api_key, config_dict=dict(self.mem0_config))

            logger.info("Initializing Mem0 Platform with API key and default configuration")
            return MemoryClient(api_key=self.mem0_api_key)
        except ImportError as e:
            msg = "Mem0 is not properly installed. Please install it with 'pip install -U mem0ai'."
            raise ImportError(msg) from e

    def ingest_data(self) -> MemoryClient:
        """Ingests a new message into Mem0 Platform memory and returns the updated memory client."""
        mem0_memory = self.existing_memory or self.build_mem0()

        if not self.ingest_message or not self.user_id:
            logger.warning("Missing 'ingest_message' or 'user_id'; cannot ingest data.")
            return mem0_memory

        metadata = self.metadata or {}

        logger.info("Ingesting message for user_id: %s", self.user_id)

        try:
            mem0_memory.add(self.ingest_message, user_id=self.user_id, metadata=metadata)
        except Exception:
            logger.exception("Failed to add message to Mem0 Platform memory.")
            raise

        return mem0_memory

    def build_search_results(self) -> Data:
        """Searches the Mem0 Platform memory for related messages based on the search query and returns the results."""
        mem0_memory = self.ingest_data()
        search_query = self.search_query
        user_id = self.user_id

        logger.info("Search query: %s", search_query)

        try:
            if search_query:
                logger.info("Performing search with query on Mem0 Platform.")
                related_memories = mem0_memory.search(query=search_query, user_id=user_id)
            else:
                logger.info("Retrieving all memories for user_id: %s from Mem0 Platform", user_id)
                related_memories = mem0_memory.get_all(user_id=user_id)
        except Exception:
            logger.exception("Failed to retrieve related memories from Mem0 Platform.")
            raise

        logger.info("Related memories retrieved: %s", related_memories)
        return related_memories

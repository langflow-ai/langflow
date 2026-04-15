from lfx.base.memory.model import LCChatMemoryComponent
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.io import Output
from lfx.log.logger import logger
from lfx.schema.data import Data


class MengramMemoryComponent(LCChatMemoryComponent):
    display_name = "Mengram Memory"
    description = (
        "Store and retrieve memories using Mengram — AI memory with semantic, episodic, and procedural types. "
        "Automatically extracts facts, events, and workflows from conversations."
    )
    name = "mengram_memory"
    icon: str = "Mengram"

    inputs = [
        SecretStrInput(
            name="mengram_api_key",
            display_name="Mengram API Key",
            info="API key for Mengram (starts with 'om-'). Get one at mengram.io.",
        ),
        MessageTextInput(
            name="user_id",
            display_name="User ID",
            info="Identifier for the user associated with the memories.",
        ),
        MessageTextInput(
            name="ingest_message",
            display_name="Message to Ingest",
            info="The message content to be ingested into Mengram memory.",
        ),
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Input text for searching related memories across all memory types.",
        ),
        MessageTextInput(
            name="agent_id",
            display_name="Agent ID",
            info="Optional identifier for the agent sending the message.",
            advanced=True,
        ),
        MessageTextInput(
            name="app_id",
            display_name="App ID",
            info="Optional identifier for the application.",
            advanced=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            info="Maximum number of results per memory type.",
            value=5,
            advanced=True,
        ),
        MessageTextInput(
            name="api_url",
            display_name="API URL",
            info="Mengram API base URL.",
            value="https://mengram.io",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="search_results", display_name="Search Results", method="search_memories"),
        Output(name="cognitive_profile", display_name="Cognitive Profile", method="get_cognitive_profile"),
        Output(name="memory", display_name="Mengram Memory", method="ingest_data"),
    ]

    def _build_client(self):
        """Initialize a Mengram client instance."""
        try:
            from mengram import Mengram
        except ImportError as e:
            msg = "Mengram is not installed. Please install it with 'pip install mengram-ai'."
            raise ImportError(msg) from e
        return Mengram(api_key=self.mengram_api_key, base_url=self.api_url)

    def ingest_data(self) -> Data:
        """Ingest a message into Mengram memory and return the result."""
        client = self._build_client()

        if not self.ingest_message or not self.user_id:
            logger.warning("Missing 'ingest_message' or 'user_id'; cannot ingest data.")
            return Data(data={"status": "skipped", "reason": "missing ingest_message or user_id"})

        logger.info("Ingesting message for user_id: %s", self.user_id)

        try:
            result = client.add(
                [{"role": "user", "content": self.ingest_message}],
                user_id=self.user_id,
                agent_id=self.agent_id or None,
                app_id=self.app_id or None,
            )
        except Exception:
            logger.exception("Failed to add message to Mengram memory.")
            raise

        return Data(data={"status": "success", "result": result})

    def search_memories(self) -> Data:
        """Search Mengram memory for related memories across all memory types."""
        client = self._build_client()

        if not self.search_query or not self.user_id:
            logger.warning("Missing 'search_query' or 'user_id'; cannot search.")
            return Data(data={})

        logger.info("Searching memories for user_id: %s", self.user_id)

        try:
            results = client.search_all(
                self.search_query,
                limit=self.top_k,
                user_id=self.user_id,
            )
        except Exception:
            logger.exception("Failed to search Mengram memory.")
            raise

        return Data(data=results)

    def get_cognitive_profile(self) -> Data:
        """Get the Cognitive Profile — a system prompt generated from all memory types."""
        client = self._build_client()

        if not self.user_id:
            logger.warning("Missing 'user_id'; cannot get cognitive profile.")
            return Data(data={"system_prompt": ""})

        logger.info("Getting cognitive profile for user_id: %s", self.user_id)

        try:
            profile = client.get_profile(self.user_id)
        except Exception:
            logger.exception("Failed to get Mengram cognitive profile.")
            raise

        return Data(data=profile)

from typing import Any, Protocol

from lfx.base.memory.model import LCChatMemoryComponent
from lfx.inputs.inputs import (
    DictInput,
    DropdownInput,
    FloatInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
)
from lfx.io import Output
from lfx.log.logger import logger
from lfx.schema.data import Data

SEARCH_MODES = ["hybrid", "memories", "chunks"]


class Memory(Protocol):
    def add(self, namespace: str, *, content: str, **kwargs: Any) -> Any: ...

    def search(self, namespace: str, *, query: str, **kwargs: Any) -> Any: ...

    def profile(self, namespace: str) -> Any: ...


def _fact_to_dict(fact: Any) -> dict[str, Any]:
    return {"id": fact.id, "memory": fact.memory}


class SupermemoryMemoryComponent(LCChatMemoryComponent):
    display_name = "Supermemory Chat Memory"
    description = "Retrieves and stores chat messages using Supermemory."
    documentation = "https://supermemory.ai/docs"
    name = "supermemory_chat_memory"
    icon: str = "Supermemory"
    inputs = [
        SecretStrInput(
            name="supermemory_api_key",
            display_name="Supermemory API Key",
            info="API key for Supermemory. Create one at https://console.supermemory.ai.",
        ),
        MessageTextInput(
            name="namespace",
            display_name="Namespace",
            info="Identifier that isolates memories, such as a user ID or a project ID.",
        ),
        MessageTextInput(
            name="ingest_message",
            display_name="Message to Ingest",
            info="The message content to be ingested into Supermemory.",
        ),
        HandleInput(
            name="existing_memory",
            display_name="Existing Memory Instance",
            input_types=["Memory"],
            info="Optional existing Supermemory client. If not provided, a new client will be created.",
        ),
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Input text for searching related memories in Supermemory.",
        ),
        MessageTextInput(
            name="document_id",
            display_name="Document ID",
            info=(
                "Optional ID for the ingested document. Reuse the same ID for one conversation or session "
                "so new messages are appended to the same document."
            ),
            advanced=True,
        ),
        DictInput(
            name="metadata",
            display_name="Metadata",
            info="Additional metadata to associate with the ingested message. Values must be strings, numbers, "
            "or booleans.",
            advanced=True,
        ),
        IntInput(
            name="search_limit",
            display_name="Search Limit",
            info="Maximum number of search results to return.",
            value=10,
            advanced=True,
        ),
        DropdownInput(
            name="search_mode",
            display_name="Search Mode",
            info="'hybrid' combines memories with source chunks, 'memories' returns learned context only, "
            "and 'chunks' returns source passages only.",
            options=SEARCH_MODES,
            value="hybrid",
            advanced=True,
        ),
        FloatInput(
            name="threshold",
            display_name="Threshold",
            info="Minimum relevance score from 0 to 1. Raise it for fewer, more precise results.",
            value=0.3,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="memory", display_name="Supermemory Memory", method="ingest_data"),
        Output(
            name="search_results",
            display_name="Search Results",
            method="build_search_results",
        ),
        Output(name="profile", display_name="Profile", method="build_profile"),
    ]

    def build_supermemory(self) -> Memory:
        """Initializes a Supermemory client with the provided API key."""
        if not self.supermemory_api_key:
            msg = "Supermemory API key is required."
            raise ValueError(msg)

        try:
            from supermemory import Supermemory
        except ImportError as e:
            msg = "Supermemory is not properly installed. Please install it with 'pip install \"supermemory>=5,<6\"'."
            raise ImportError(msg) from e

        return Supermemory(api_key=self.supermemory_api_key)

    def ingest_data(self) -> Memory:
        """Ingests a new message into Supermemory and returns the client."""
        supermemory = self.existing_memory or self.build_supermemory()

        if not self.ingest_message or not self.namespace:
            logger.warning("Missing 'ingest_message' or 'namespace'; cannot ingest data.")
            return supermemory

        kwargs: dict[str, Any] = {}
        if self.document_id:
            kwargs["id"] = self.document_id
        if self.metadata:
            kwargs["metadata"] = self.metadata

        logger.info("Ingesting message for namespace: %s", self.namespace)

        try:
            supermemory.add(self.namespace, content=self.ingest_message, **kwargs)
        except Exception:
            logger.exception("Failed to add message to Supermemory.")
            raise

        return supermemory

    def build_search_results(self) -> Data:
        """Searches Supermemory for content related to the search query and returns the results."""
        supermemory = self.ingest_data()

        if not self.search_query or not self.namespace:
            logger.warning("Missing 'search_query' or 'namespace'; returning no search results.")
            return Data(data={"results": []})

        logger.info("Searching Supermemory namespace: %s", self.namespace)

        try:
            response = supermemory.search(
                self.namespace,
                query=self.search_query,
                limit=self.search_limit,
                search_mode=self.search_mode,
                threshold=self.threshold,
            )
        except Exception:
            logger.exception("Failed to retrieve related memories from Supermemory.")
            raise

        results = [
            {
                "id": result.id,
                "memory": result.memory,
                "chunk": result.chunk,
                "similarity": result.similarity,
                "metadata": result.metadata,
            }
            for result in response.results
        ]
        logger.info("Related memories retrieved: %s", len(results))
        return Data(data={"results": results})

    def build_profile(self) -> Data:
        """Retrieves the profile that Supermemory maintains for the namespace."""
        supermemory = self.existing_memory or self.build_supermemory()

        if not self.namespace:
            logger.warning("Missing 'namespace'; returning an empty profile.")
            return Data(data={"static": [], "dynamic": [], "buckets": {}})

        try:
            response = supermemory.profile(self.namespace)
        except Exception:
            logger.exception("Failed to retrieve the profile from Supermemory.")
            raise

        profile = response.profile
        return Data(
            data={
                "static": [_fact_to_dict(fact) for fact in profile.static],
                "dynamic": [_fact_to_dict(fact) for fact in profile.dynamic],
                "buckets": {name: [_fact_to_dict(fact) for fact in facts] for name, facts in profile.buckets.items()},
            }
        )

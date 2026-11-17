from typing import Any, Protocol

from lfx.base.memory.model import LCChatMemoryComponent
from lfx.inputs.inputs import (
    DictInput,
    FloatInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
)
from lfx.io import Output
from lfx.log.logger import logger
from lfx.schema.data import Data


class Memory(Protocol):
    def write(self, content: str, **kwargs: Any) -> Any: ...

    def read(self, query: str, **kwargs: Any) -> Any: ...


class MnemoverseMemoryComponent(LCChatMemoryComponent):
    display_name = "Mnemoverse Chat Memory"
    description = "Stores and recalls chat messages using Mnemoverse, a memory that agents share across tools."
    documentation = "https://mnemoverse.com/docs/api/python-sdk"
    name = "mnemoverse_chat_memory"
    icon: str = "Mnemoverse"
    inputs = [
        SecretStrInput(
            name="mnemoverse_api_key",
            display_name="Mnemoverse API Key",
            info="API key for Mnemoverse. Create one at https://console.mnemoverse.com.",
        ),
        MessageTextInput(
            name="domain",
            display_name="Domain",
            info="Namespace that isolates memories, such as user:<id> or project:<name>. "
            "Leave empty to store in the general domain and search the account's own domains.",
        ),
        MessageTextInput(
            name="ingest_message",
            display_name="Message to Ingest",
            info="The message content to store in Mnemoverse.",
        ),
        HandleInput(
            name="existing_memory",
            display_name="Existing Memory Instance",
            input_types=["Memory"],
            info="Optional existing Mnemoverse client. If not provided, a new client will be created.",
        ),
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Natural-language query for related memories in Mnemoverse.",
        ),
        DictInput(
            name="metadata",
            display_name="Metadata",
            info="Additional metadata to store with the ingested message.",
            advanced=True,
        ),
        IntInput(
            name="top_k",
            display_name="Search Limit",
            info="Maximum number of memories to return.",
            value=10,
            advanced=True,
        ),
        FloatInput(
            name="min_relevance",
            display_name="Minimum Relevance",
            info="Minimum relevance score from 0 to 1. Raise it for fewer, more precise results.",
            value=0.3,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="memory", display_name="Mnemoverse Memory", method="ingest_data"),
        Output(name="search_results", display_name="Search Results", method="build_search_results"),
    ]

    def build_mnemoverse(self) -> Memory:
        """Initializes a Mnemoverse client with the provided API key."""
        if not self.mnemoverse_api_key:
            msg = "Mnemoverse API key is required."
            raise ValueError(msg)

        try:
            from mnemoverse import MnemoClient
        except ImportError as e:
            msg = "Mnemoverse is not properly installed. Please install it with 'pip install \"mnemoverse>=0.5,<1\"'."
            raise ImportError(msg) from e

        return MnemoClient(api_key=self.mnemoverse_api_key)

    def _domain_kwargs(self) -> dict[str, Any]:
        return {"domain": self.domain} if self.domain else {}

    @staticmethod
    def _release(client: Memory) -> None:
        """Closes the client's event loop and connection pool after a call.

        Inside a running event loop the synchronous MnemoClient serves its calls
        from a daemon thread that lives until close(). A long-running Langflow
        server would keep one such thread per run, so every call is followed by
        close(). The client stays usable afterwards: the next call opens a fresh
        loop and connection, so a client passed on through the Memory output
        keeps working.
        """
        close = getattr(client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001
                logger.debug("Closing the Mnemoverse client failed.", exc_info=True)

    def ingest_data(self) -> Memory:
        """Stores a new message in Mnemoverse and returns the client."""
        mnemoverse = self.existing_memory or self.build_mnemoverse()

        if not self.ingest_message:
            logger.warning("Missing 'ingest_message'; nothing to store.")
            return mnemoverse

        kwargs = self._domain_kwargs()
        if self.metadata:
            kwargs["metadata"] = self.metadata

        logger.info("Storing message in Mnemoverse domain: %s", self.domain or "default")

        try:
            mnemoverse.write(self.ingest_message, **kwargs)
        except Exception:
            logger.exception("Failed to store message in Mnemoverse.")
            raise
        finally:
            self._release(mnemoverse)

        return mnemoverse

    def build_search_results(self) -> Data:
        """Searches Mnemoverse for memories related to the search query and returns the results."""
        mnemoverse = self.ingest_data()

        if not self.search_query:
            logger.warning("Missing 'search_query'; returning no search results.")
            return Data(data={"results": []})

        logger.info("Searching Mnemoverse domain: %s", self.domain or "default")

        try:
            response = mnemoverse.read(
                self.search_query,
                top_k=self.top_k,
                min_relevance=self.min_relevance,
                **self._domain_kwargs(),
            )
        except Exception:
            logger.exception("Failed to retrieve related memories from Mnemoverse.")
            raise
        finally:
            self._release(mnemoverse)

        results = [
            {
                "id": str(item.atom_id),
                "memory": item.content,
                "relevance": item.relevance,
                "domain": item.domain,
                "metadata": item.metadata,
            }
            for item in response.items
        ]
        logger.info("Related memories retrieved: %s", len(results))
        return Data(data={"results": results})

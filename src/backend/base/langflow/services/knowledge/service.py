"""Independent KnowledgeHub service for managing knowledge hub interactions."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import aiohttp
from langflow.services.base import Service

from .settings import KnowledgeSettings

logger = logging.getLogger(__name__)


class KnowledgeService(Service):
    """Independent KnowledgeHub service for managing knowledge hub interactions."""

    name = "knowledge_service"

    def __init__(self):
        """Initialize the Knowledge service."""
        super().__init__()
        # Initialize settings from environment variables
        self.settings = KnowledgeSettings()
        self._http_client: Optional[aiohttp.ClientSession] = None
        self._hub_cache: Optional[List[Dict[str, str]]] = None
        self._ready = False

    def set_ready(self) -> None:
        """Set the service as ready."""
        if not self.settings.is_configured():
            logger.warning("KnowledgeHub settings are not properly configured, service will run in limited mode")
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if the service is ready."""
        return self._ready

    @property
    def http_client(self) -> aiohttp.ClientSession:
        """Get the HTTP client, initializing it if necessary."""
        if not self._http_client or self._http_client.closed:
            self._http_client = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.settings.TIMEOUT),
                headers={"User-Agent": self.settings.USER_AGENT},
            )
        return self._http_client

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._http_client and not self._http_client.closed:
            await self._http_client.close()
            self._http_client = None
            logger.debug("KnowledgeHub HTTP client closed")

    @asynccontextmanager
    async def get_client(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        """Context manager for getting an HTTP client."""
        try:
            yield self.http_client
        finally:
            pass

    # Legacy API methods for backward compatibility
    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for knowledge documents (synchronous wrapper).

        Args:
            query: Search query string
            **kwargs: Additional search parameters

        Returns:
            List of documents matching the query
        """
        import asyncio

        try:
            # Run the async method in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                knowledge_hubs = loop.run_until_complete(self.get_knowledge_hubs())
                if not knowledge_hubs:
                    return []

                # Use all available knowledge hubs for the search
                hub_ids = [hub["id"] for hub in knowledge_hubs if hub.get("id")]
                if not hub_ids:
                    return []

                results = loop.run_until_complete(
                    self.query_vector_store(hub_ids, query, **kwargs)
                )
                return results if isinstance(results, list) else []
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in search: {e}")
            return []

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID (synchronous wrapper).

        Args:
            doc_id: Document identifier

        Returns:
            Document data if found, None otherwise
        """
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Implementation would depend on specific document API
                # For now, return None as this requires additional endpoint
                logger.warning(f"Direct document retrieval by ID {doc_id} not yet implemented")
                return None
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error getting document {doc_id}: {e}")
            return None

    def list_collections(self) -> List[str]:
        """List available knowledge collections (synchronous wrapper).

        Returns:
            List of collection names
        """
        try:
            # Try to use existing event loop if available
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an event loop, we can't use run_until_complete
                    # Return empty list with warning for now
                    logger.warning("Cannot list collections from within running event loop")
                    return []
                else:
                    hubs = loop.run_until_complete(self.get_knowledge_hubs())
                    return [hub.get("name", "") for hub in hubs if hub.get("name")]
            except RuntimeError:
                # No event loop, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    hubs = loop.run_until_complete(self.get_knowledge_hubs())
                    return [hub.get("name", "") for hub in hubs if hub.get("name")]
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return []

    # Async API methods
    async def get_knowledge_hubs(self) -> List[Dict[str, str]]:
        """Fetch the list of knowledge hub names and IDs."""
        if not self.ready:
            logger.error("KnowledgeHub service is not ready")
            return []

        if self._hub_cache is not None:
            return self._hub_cache

        try:
            url = f"{self.settings.ENDPOINT_URL}/v1/clients/{self.settings.GENESIS_CLIENT_ID}/knowledge-hub"

            async with self.get_client() as client:
                async with client.get(
                    url,
                    headers={"accept": "application/json"},
                ) as response:
                    response.raise_for_status()
                    data = (await response.json()).get("data", [])

            logger.info(f"KnowledgeHub data: {data}")

            self._hub_cache = [
                {
                    "name": item.get("name", item.get("name", "Unknown")),
                    "id": item.get("id"),
                }
                for item in data
            ]
            return self._hub_cache

        except Exception as e:
            logger.error(f"Error fetching knowledge hub names: {e}")
            return []

    async def query_vector_store(
        self,
        knowledge_hub_ids: List[str],
        query: str,
        embedding_model: str = "embedding-bge-base-3",
        top_k: int = 20,
    ) -> List[Any]:
        """Query the vector store with the given parameters."""
        if not self.ready:
            logger.error("KnowledgeHub service is not ready")
            return []

        try:
            url = f"{self.settings.ENDPOINT_URL}/v1/clients/{self.settings.GENESIS_CLIENT_ID}/knowledge-hub/query"

            payload = {
                "knowledgeHubIds": knowledge_hub_ids,
                "query": query,
                "embeddingModel": embedding_model,
                "topK": top_k,
            }

            async with self.get_client() as client:
                async with client.post(
                    url,
                    headers={
                        "accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("data", {}).get("result", [])

        except Exception as e:
            logger.error(f"Error querying vector store: {e}")
            return []

    async def get_knowledge_hub_documents(
        self, knowledge_hub_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch documents from a specific knowledge hub."""
        if not self.ready:
            logger.error("KnowledgeHub service is not ready")
            return []

        if not knowledge_hub_id:
            logger.error("Knowledge hub ID is required")
            return []

        try:
            url = f"{self.settings.ENDPOINT_URL}/v1/clients/{self.settings.GENESIS_CLIENT_ID}/knowledge-hub-documents"

            async with self.get_client() as client:
                async with client.get(
                    url,
                    params={
                        "knowledge_hub_id": knowledge_hub_id,
                        "search_term": "",
                        "page": 1,
                        "page_size": 1000,
                        "has_decision_tree": "false",
                    },
                    headers={"accept": "application/json"},
                ) as response:
                    response.raise_for_status()
                    response_data = await response.json()

                    # Validate response data structure
                    if not isinstance(response_data, dict):
                        logger.error(f"Invalid response format: {response_data}")
                        return []

                    data = response_data.get("data", {}).get("items", [])
                    if not isinstance(data, list):
                        logger.error(f"Invalid data format: {data}")
                        return []

                    # Process the documents data with additional validation
                    documents = []
                    for doc in data:
                        if not isinstance(doc, dict):
                            logger.warning(f"Skipping invalid document format: {doc}")
                            continue

                        # Skip deleted documents
                        if doc.get("isDeleted", False):
                            continue

                        # Ensure required fields are present
                        doc_id = doc.get("id")
                        doc_name = doc.get("name")
                        if not doc_id or not doc_name:
                            logger.warning(
                                f"Skipping document with missing required fields: {doc}"
                            )
                            continue

                        documents.append(
                            {
                                "id": doc_id,
                                "name": doc_name,
                                "type": doc.get("documentType"),
                                "uuid": doc.get("documentUUID"),
                                "created_at": doc.get("createdAt"),
                                "updated_at": doc.get("updatedAt"),
                                "folder": (
                                    doc_name.split("/")[0] if "/" in doc_name else None
                                ),
                            }
                        )

                    return documents

        except aiohttp.ClientResponseError as e:
            logger.error(
                f"HTTP error fetching knowledge hub documents: {e.status}, {e.message}"
            )
            return []
        except Exception as e:
            logger.error(f"Error fetching knowledge hub documents: {e}")
            return []

    async def get_document_signed_url(
        self, knowledge_hub_id: str, file_path: str
    ) -> Optional[str]:
        """Get a signed URL for a specific document.

        Args:
            knowledge_hub_id: ID of the knowledge hub
            file_path: Full path of the file within the knowledge hub

        Returns:
            Signed URL if successful, None otherwise
        """
        if not self.ready:
            logger.error("KnowledgeHub service is not ready")
            return None

        try:
            url = f"{self.settings.ENDPOINT_URL}/v1/clients/{self.settings.GENESIS_CLIENT_ID}/knowledge-hub/{knowledge_hub_id}/files/signed-url"

            logger.debug(f"Getting signed URL for file: {file_path}")
            logger.debug(f"URL: {url}")

            async with self.get_client() as client:
                async with client.post(
                    url,
                    params={
                        "file_name": file_path
                    },  # Use params for query parameters
                    headers={
                        "accept": "application/json",
                        "Content-Type": "application/json",
                    },
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    logger.debug(f"Response data: {data}")
                    return data.get("data", {}).get(
                        "signedUrl"
                    )  # Handle nested response structure

        except Exception as e:
            logger.error(f"Error getting signed URL for file {file_path}: {e}")
            return None
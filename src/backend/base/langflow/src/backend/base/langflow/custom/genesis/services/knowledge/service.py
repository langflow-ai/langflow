# services/knowledge/service.py
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from langflow.services.base import Service
from loguru import logger

from .settings import KnowledgeSettings


class KnowledgeService(Service):
    """Independent KnowledgeHub service for managing knowledgehub hub interactions."""

    name = "knowledge_service"

    def __init__(self):
        super().__init__()
        # Initialize settings from environment variables
        self.settings = KnowledgeSettings()
        self._http_client: aiohttp.ClientSession | None = None
        self._hub_cache: list[dict[str, str]] | None = None
        self._ready = False

    def set_ready(self) -> None:
        """Set the service as ready."""
        if not self.settings.is_configured():
            raise ValueError("KnowledgeHub settings are not properly configured")
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

    async def get_knowledge_hubs(self) -> list[dict[str, str]]:
        """Fetch the list of knowledgehub hub names and IDs."""
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
            logger.error(f"Error fetching knowledgehub hub names: {e!s}")
            return []

    async def query_vector_store(
        self,
        knowledge_hub_ids: list[str],
        query: str,
        embedding_model: str = "bge_base",
        top_k: int = 20,
    ) -> list[Any]:
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
            logger.error(f"Error querying vector store: {e!s}")
            return []

    async def get_knowledge_hub_documents(
        self, knowledge_hub_id: str
    ) -> list[dict[str, Any]]:
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

                    data = response_data.get("data", []).get("items", [])
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
            logger.error(f"Error fetching knowledge hub documents: {e!s}")
            return []

    async def get_document_signed_url(
        self, knowledge_hub_id: str, file_path: str
    ) -> str | None:
        """Get a signed URL for a specific document.

        Args:
            knowledge_hub_id (str): ID of the knowledge hub
            file_path (str): Full path of the file within the knowledge hub

        Returns:
            Optional[str]: Signed URL if successful, None otherwise
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
                    },  # Use json parameter for automatic JSON encoding
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
            logger.error(f"Error getting signed URL for file {file_path}: {e!s}")
            return None

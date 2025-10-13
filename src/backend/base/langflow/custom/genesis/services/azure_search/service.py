"""Azure AI Search service for vector operations."""

from typing import Any

from langflow.services.base import Service
from loguru import logger

from .settings import AzureSearchSettings


class AzureSearchService(Service):
    """Service for Azure AI Search vector operations."""

    name = "azure_search_service"

    def __init__(self):
        super().__init__()
        self.settings = AzureSearchSettings()
        self._client = None
        self._ready = False

    def set_ready(self) -> None:
        """Set the service as ready."""
        if not self.settings.is_configured():
            raise ValueError("Azure AI Search settings are not properly configured")
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if the service is ready."""
        return self._ready

    def get_client(self, index_name: str):
        """Get Azure Search client for specific index."""
        if not self.ready:
            raise ValueError("Azure Search service is not ready")

        try:
            from azure.search.documents import SearchClient
            from azure.core.credentials import AzureKeyCredential

            return SearchClient(
                endpoint=self.settings.AZURE_SEARCH_ENDPOINT,
                index_name=index_name,
                credential=AzureKeyCredential(self.settings.AZURE_SEARCH_API_KEY),
                api_version=self.settings.AZURE_SEARCH_API_VERSION,
            )
        except ImportError as e:
            logger.error(f"Azure Search SDK not installed: {e}")
            raise

    async def search(self, index_name: str, query: str, top_k: int = 10, **kwargs) -> list[dict[str, Any]]:
        """Search the specified index."""
        if not self.ready:
            logger.error("Azure Search service is not ready")
            return []

        try:
            client = self.get_client(index_name)

            # Handle parameter conflicts - if 'top' is passed in kwargs, use that instead of top_k
            search_params = kwargs.copy()
            if 'top' in search_params:
                # Use the explicitly passed 'top' parameter
                final_top = search_params.pop('top')
            else:
                final_top = top_k

            results = client.search(
                search_text=query,
                top=final_top,
                **search_params
            )
            return [dict(result) for result in results]
        except Exception as e:
            logger.error(f"Error searching Azure AI Search index '{index_name}': {e}")
            return []

    async def index_documents(self, index_name: str, documents: list[dict[str, Any]]) -> bool:
        """Index documents in the specified search index."""
        if not self.ready:
            logger.error("Azure Search service is not ready")
            return False

        try:
            client = self.get_client(index_name)
            result = client.upload_documents(documents)
            logger.info(f"Indexed {len(documents)} documents in '{index_name}'")
            return True
        except Exception as e:
            logger.error(f"Error indexing documents in '{index_name}': {e}")
            return False

    async def search_vector(self, index_name: str, vector: list[float], top_k: int = 10, **kwargs) -> list[dict[str, Any]]:
        """Vector similarity search in the specified index."""
        if not self.ready:
            logger.error("Azure Search service is not ready")
            return []

        try:
            from azure.search.documents.models import VectorizedQuery

            client = self.get_client(index_name)
            # Vector search using Azure AI Search vector capabilities
            vector_query = VectorizedQuery(vector=vector, k=top_k, fields="vector")
            results = client.search(
                vector_queries=[vector_query],
                **kwargs
            )
            return [{"result": dict(result), "distance": getattr(result, "@search.score", 0.0)}
                   for result in results]
        except Exception as e:
            logger.error(f"Error in vector search for '{index_name}': {e}")
            return []

    async def search_components(
        self,
        query_text: str,
        query_vector: list[float],
        capabilities: list[str] = None,
        top_k: int = 5,
        **filters
    ) -> list[dict[str, Any]]:
        """Combined component search using multiple indexes."""
        if not self.ready:
            logger.error("Azure Search service is not ready")
            return []

        try:
            # 1. Semantic similarity search on component-embeddings
            semantic_results = await self.search_vector(
                "component-embeddings",
                query_vector,
                top_k=top_k * 2  # Get more for filtering
            )

            if not semantic_results:
                return []

            # 2. Capability matching on capability-embeddings (if capabilities provided)
            capability_scores = {}
            if capabilities:
                for cap in capabilities:
                    cap_vector = query_vector  # Using same vector for simplicity
                    cap_results = await self.search_vector(
                        "capability-embeddings",
                        cap_vector,
                        top_k=top_k
                    )
                    for result in cap_results:
                        comp_id = result["result"].get("component_id")
                        if comp_id:
                            capability_scores[comp_id] = max(
                                capability_scores.get(comp_id, 0),
                                result.get("distance", 0)
                            )

            # 3. Metadata filtering on component-metadata
            filtered_results = []
            for item in semantic_results:
                result = item["result"]
                component_id = result.get("id") or result.get("component_key")

                # Check metadata filters
                include_result = True
                for filter_key, filter_value in filters.items():
                    if result.get(filter_key) != filter_value:
                        include_result = False
                        break

                if include_result:
                    # Combine scores
                    semantic_score = item.get("distance", 0.0)
                    capability_score = capability_scores.get(component_id, 0.0)

                    combined_score = self._combine_scores(
                        semantic_score, capability_score, True
                    )

                    filtered_results.append({
                        "component_id": component_id,
                        "score": combined_score,
                        "semantic_score": semantic_score,
                        "capability_score": capability_score,
                        "metadata": result
                    })

            # Sort by combined score and return top_k
            filtered_results.sort(key=lambda x: x["score"], reverse=True)
            return filtered_results[:top_k]

        except Exception as e:
            logger.error(f"Error in combined component search: {e}")
            return []

    def _combine_scores(self, semantic_score: float, capability_score: float, metadata_match: bool) -> float:
        """Combine semantic, capability, and metadata scores."""
        base_score = semantic_score * 0.7 + capability_score * 0.3
        return base_score if metadata_match else base_score * 0.5

    # Index-specific methods for Agent Builder

    async def search_component_embeddings(self, query_vector: list[float], top_k: int = 10, **filters) -> list[dict[str, Any]]:
        """Search component embeddings for semantic similarity."""
        return await self.search_vector("component-embeddings", query_vector, top_k=top_k, **filters)

    async def index_component_embeddings(self, documents: list[dict[str, Any]]) -> bool:
        """Index documents in component-embeddings index."""
        return await self.index_documents("component-embeddings", documents)

    async def search_capability_embeddings(self, query_vector: list[float], top_k: int = 10, **filters) -> list[dict[str, Any]]:
        """Search capability embeddings for capability matching."""
        return await self.search_vector("capability-embeddings", query_vector, top_k=top_k, **filters)

    async def index_capability_embeddings(self, documents: list[dict[str, Any]]) -> bool:
        """Index documents in capability-embeddings index."""
        return await self.index_documents("capability-embeddings", documents)

    async def search_component_metadata(self, filters: dict[str, Any], top_k: int = 10) -> list[dict[str, Any]]:
        """Search component metadata with filters."""
        filter_expr = " and ".join([f"{k} eq '{v}'" for k, v in filters.items()])
        return await self.search("component-metadata", "*", top_k=top_k, filter=filter_expr)

    async def index_component_metadata(self, documents: list[dict[str, Any]]) -> bool:
        """Index documents in component-metadata index."""
        return await self.index_documents("component-metadata", documents)

    async def search_agent_metadata(self, filters: dict[str, Any], top_k: int = 10) -> list[dict[str, Any]]:
        """Search agent metadata with filters."""
        filter_expr = " and ".join([f"{k} eq '{v}'" for k, v in filters.items()])
        return await self.search("agent-metadata", "*", top_k=top_k, filter=filter_expr)

    async def index_agent_metadata(self, documents: list[dict[str, Any]]) -> bool:
        """Index documents in agent-metadata index."""
        return await self.index_documents("agent-metadata", documents)

    async def cleanup(self) -> None:
        """Clean up resources."""
        # Azure clients don't need explicit cleanup
        logger.debug("Azure Search service cleaned up")

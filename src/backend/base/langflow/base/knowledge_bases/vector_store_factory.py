"""Database-driven vector store factory for Knowledge Bases.

This module provides a factory function to build vector store instances
based on per-user configuration stored in the Variable service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypedDict

from langflow.services.deps import get_variable_service


class BaseKBConfig(TypedDict, total=False):
    """Base configuration for Knowledge Base providers."""

    kb_provider: str


class ChromaKBConfig(BaseKBConfig, total=False):
    """Type definition for Chroma Knowledge Base configuration."""

    # Chroma-specific configuration
    kb_chroma_server_host: str
    kb_chroma_server_http_port: str
    kb_chroma_server_ssl_enabled: str | bool


class OpenSearchKBConfig(BaseKBConfig, total=False):
    """Type definition for OpenSearch Knowledge Base configuration."""

    # OpenSearch-specific configuration
    kb_opensearch_url: str
    kb_opensearch_index_prefix: str
    kb_opensearch_username: str
    kb_opensearch_password: str
    kb_opensearch_verify_certs: str | bool


# Union type for all possible KB configurations
KBConfig = ChromaKBConfig | OpenSearchKBConfig


if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

    from opensearchpy import OpenSearch
    from sqlmodel.ext.asyncio.session import AsyncSession


class VectorStoreProtocol(Protocol):
    """Protocol for vector store instances compatible with metadata adapters.

    This protocol defines the minimum interface required for vector stores
    to work with the metadata adapter system. Our adapters implement this
    protocol while encapsulating the underlying vector store implementations.
    """

    def get(self, **kwargs: Any) -> dict[str, Any]:
        """Get documents and metadata from the vector store."""
        ...

    def add_documents(self, documents: list[Any], **kwargs: Any) -> list[str]:
        """Add documents to the vector store."""
        ...

    def similarity_search(self, query: str, k: int = 4, **kwargs: Any) -> list[Any]:
        """Perform similarity search."""
        ...

    def similarity_search_with_score(self, query: str, k: int = 4, **kwargs: Any) -> list[tuple[Any, float]]:
        """Perform similarity search with scores."""
        ...


class OpenSearchVectorStoreAdapter:
    """Adapter for OpenSearch clients to implement VectorStoreProtocol."""

    def __init__(self, opensearch_client: OpenSearch, index_name: str, component: Any = None):
        """Initialize the OpenSearch adapter.

        Args:
            opensearch_client: OpenSearch client instance
            index_name: Name of the index to use
            component: Optional OpenSearchVectorStoreComponent for advanced operations
        """
        self._client = opensearch_client
        self.index_name = index_name
        self._component = component
        # Store index name on client for metadata adapter
        self._client._index_name = index_name

    def get(self, **kwargs: Any) -> dict[str, Any]:
        """Get documents and metadata from OpenSearch."""
        try:
            response = self._client.search(
                index=self.index_name,
                body={
                    "query": {"match_all": {}},
                    "size": kwargs.get("limit", 1000),
                    "_source": True,
                },
            )

            hits = response.get("hits", {}).get("hits", [])
            documents = []
            metadatas = []

            for hit in hits:
                source = hit.get("_source", {})
                text = source.get("text", "")
                documents.append(text)

                metadata = {k: v for k, v in source.items() if k != "text"}
                metadatas.append(metadata)

        except (AttributeError, KeyError, ValueError):
            return {"documents": [], "metadatas": []}
        else:
            return {"documents": documents, "metadatas": metadatas}

    def add_documents(self, documents: list[Any], **kwargs: Any) -> list[str]:
        """Add documents to OpenSearch using component's bulk ingestion."""
        try:
            texts = []
            metadatas = []

            for doc in documents:
                if hasattr(doc, "page_content"):
                    texts.append(doc.page_content)
                    metadatas.append(getattr(doc, "metadata", {}))
                else:
                    texts.append(str(doc))
                    metadatas.append({})

            return self._component._bulk_ingest_embeddings(
                client=self._client,
                index_name=self.index_name,
                embeddings=kwargs.get("embeddings", []),
                texts=texts,
                metadatas=metadatas,
                **kwargs,
            )

        except (AttributeError, ImportError):
            return []

    def similarity_search(self, query: str, k: int = 4, **_kwargs: Any) -> list[Any]:
        """Perform similarity search using OpenSearch component's advanced search."""
        try:
            search_results = self._component.search(query)
            from lfx.schema.data import Data

            limited_results = search_results[:k] if len(search_results) > k else search_results

            return [
                Data(text=result.get("page_content", ""), **result.get("metadata", {})) for result in limited_results
            ]

        except (AttributeError, ImportError, KeyError):
            return []

    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to the underlying OpenSearch client."""
        return getattr(self._client, name)


class ChromaVectorStoreAdapter:
    """Adapter that wraps LangChain Chroma vector store to implement our protocol."""

    def __init__(self, langchain_store: Any):
        """Initialize with a LangChain Chroma vector store."""
        self._store = langchain_store

    def get(self, **kwargs: Any) -> dict[str, Any]:
        """Get documents and metadata from Chroma."""
        return self._store.get(**kwargs)

    def add_documents(self, documents: list[Any], **kwargs: Any) -> list[str]:
        """Add documents to Chroma."""
        return self._store.add_documents(documents, **kwargs)

    def similarity_search(self, query: str, k: int = 4, **kwargs: Any) -> list[Any]:
        """Perform similarity search with Chroma."""
        return self._store.similarity_search(query, k=k, **kwargs)

    def similarity_search_with_score(self, query: str, k: int = 4, **kwargs: Any) -> list[tuple[Any, float]]:
        """Perform similarity search with scores."""
        return self._store.similarity_search_with_score(query, k=k, **kwargs)

    # Expose Chroma-specific attributes for metadata adapters
    @property
    def _collection(self) -> Any:
        """Access to underlying Chroma collection."""
        return getattr(self._store, "_collection", None)

    @property
    def _client(self) -> Any:
        """Access to underlying Chroma client."""
        return getattr(self._store, "_client", None)


def _normalize_bool(value: Any) -> bool:
    """Normalize string boolean values from environment variables."""
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)


def _normalize_int(value: Any) -> int | None:
    """Normalize string integer values from environment variables."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return int(value)


async def build_kb_vector_store(
    kb_path: Path,
    collection_name: str,
    embedding_function: Any | None,
    user_id: UUID,
    session: AsyncSession,
) -> ChromaVectorStoreAdapter | OpenSearchVectorStoreAdapter:
    """Build a vector store instance based on user's KB configuration from database.

    Args:
        kb_path: Path to the knowledge base directory
        collection_name: Name of the collection/index
        embedding_function: Embedding function to use
        user_id: User ID for configuration lookup
        session: Database session

    Returns:
            ChromaVectorStoreAdapter or OpenSearchVectorStoreAdapter instance

    Raises:
            ValueError: If provider is not supported
            ImportError: If required dependencies are not available
    """
    variable_service = get_variable_service()
    kb_vars = await variable_service.get_by_category(user_id, "KB", session)
    config: KBConfig = {var.name: var.value for var in kb_vars}  # type: ignore[misc]

    provider = config.get("kb_provider", "chroma").lower()

    if provider == "chroma":
        chroma_config: ChromaKBConfig = config  # type: ignore[assignment]
        return await _build_chroma_store(kb_path, collection_name, embedding_function, chroma_config)
    if provider == "opensearch":
        opensearch_config: OpenSearchKBConfig = config  # type: ignore[assignment]
        opensearch_client, component = _build_opensearch_store(
            kb_path, collection_name, embedding_function, opensearch_config
        )
        index_name = f"{config.get('kb_opensearch_index_prefix', 'kb-')}{collection_name}"
        return OpenSearchVectorStoreAdapter(opensearch_client, index_name, component)
    error_msg = f"Unsupported vector store provider: {provider}"
    raise ValueError(error_msg)


async def _build_chroma_store(
    kb_path: Path,
    collection_name: str,
    embedding_function: Any | None,
    config: ChromaKBConfig,
) -> ChromaVectorStoreAdapter:
    """Build a Chroma vector store instance."""
    try:
        from langchain_chroma import Chroma
    except ImportError as e:
        msg = "Could not import Chroma integration package. Please install it with `pip install langchain-chroma`."
        raise ImportError(msg) from e

    persist_directory = config.get("kb_chroma_persist_directory", str(kb_path))

    chroma_server_host = config.get("kb_chroma_server_host")
    chroma_server_http_port = _normalize_int(config.get("kb_chroma_server_http_port"))
    chroma_server_ssl_enabled = _normalize_bool(config.get("kb_chroma_server_ssl_enabled", False))

    client_settings = None
    if chroma_server_host and chroma_server_http_port:
        from chromadb import HttpClient

        client = HttpClient(
            host=chroma_server_host,
            port=chroma_server_http_port,
            ssl=chroma_server_ssl_enabled,
        )
        chroma_store = Chroma(
            client=client,
            collection_name=collection_name,
            embedding_function=embedding_function,
        )
    else:
        chroma_store = Chroma(
            persist_directory=persist_directory,
            collection_name=collection_name,
            embedding_function=embedding_function,
            client_settings=client_settings,
        )

    return ChromaVectorStoreAdapter(chroma_store)


def _build_opensearch_store(
    _kb_path: Path,
    collection_name: str,
    _embedding_function: Any | None,
    config: OpenSearchKBConfig,
) -> tuple[OpenSearch, Any]:
    """Build an OpenSearch vector store instance using the real OpenSearch component."""
    from lfx.components.elastic.opensearch import OpenSearchVectorStoreComponent

    opensearch_url = config.get("kb_opensearch_url", "https://localhost:9200")
    username = config.get("kb_opensearch_username", "admin")
    password = config.get("kb_opensearch_password", "admin")
    verify_certs = _normalize_bool(config.get("kb_opensearch_verify_certs", False))
    use_ssl = opensearch_url.startswith("https")
    index_name = f"{config.get('kb_opensearch_index_prefix', 'kb-')}{collection_name}"

    component = OpenSearchVectorStoreComponent()
    component.opensearch_url = opensearch_url
    component.index_name = index_name
    component.username = username
    component.password = password
    component.verify_certs = verify_certs
    component.use_ssl = use_ssl
    component.auth_mode = "basic"

    client = OpenSearchVectorStoreComponent.build_client(
        opensearch_url=opensearch_url,
        use_ssl=use_ssl,
        verify_certs=verify_certs,
        auth_mode="basic",
        username=username,
        password=password,
    )

    client._index_name = index_name

    return client, component

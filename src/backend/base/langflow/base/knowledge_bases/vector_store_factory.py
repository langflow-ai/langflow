"""Database-driven vector store factory for Knowledge Bases.

This module provides a factory function to build vector store instances
based on per-user configuration stored in the Variable service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from langflow.services.deps import get_variable_service

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

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


class MockOpenSearchVectorStore:
    """Mock OpenSearch vector store for testing until real component is ready.

    This class implements the VectorStoreProtocol interface to ensure compatibility
    with the metadata adapter system.
    """

    def __init__(
        self,
        embedding_function: Any = None,
        opensearch_url: str | None = None,
        index_name: str | None = None,
        **kwargs: Any,
    ):
        self.embedding_function = embedding_function
        self.opensearch_url = opensearch_url
        self.index_name = index_name
        self.kwargs = kwargs
        self._documents: list[dict[str, Any]] = []

    def add_documents(self, documents: list[Any], **_kwargs: Any) -> list[str]:
        """Mock add_documents method."""
        doc_ids = [f"doc_{len(self._documents) + i}" for i in range(len(documents))]
        for i, doc in enumerate(documents):
            doc_id = doc_ids[i]
            self._documents.append(
                {
                    "id": doc_id,
                    "content": doc.page_content if hasattr(doc, "page_content") else str(doc),
                    "metadata": doc.metadata if hasattr(doc, "metadata") else {},
                }
            )
        return doc_ids

    def similarity_search(self, _query: str, k: int = 4, **_kwargs: Any) -> list[Any]:
        """Mock similarity search method."""
        from lfx.schema.data import Data

        # Simple mock: return first k documents
        return [Data(data={"text": doc["content"], **doc["metadata"]}) for doc in self._documents[:k]]

    def get(self, **kwargs: Any) -> dict[str, Any]:
        """Mock get method to retrieve documents and metadata."""
        include = kwargs.get("include", ["documents", "metadatas"])
        result: dict[str, Any] = {}

        if "documents" in include:
            result["documents"] = [doc["content"] for doc in self._documents]
        if "metadatas" in include:
            result["metadatas"] = [doc["metadata"] for doc in self._documents]
        if "ids" in include:
            result["ids"] = [doc["id"] for doc in self._documents]

        return result

    def similarity_search_with_score(self, query: str, k: int = 4, **_kwargs: Any) -> list[tuple[Any, float]]:
        """Mock similarity search with score method."""
        docs = self.similarity_search(query, k, **_kwargs)
        # Return with mock scores
        return [(doc, 0.9 - i * 0.1) for i, doc in enumerate(docs)]


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
) -> ChromaVectorStoreAdapter | MockOpenSearchVectorStore:
    """Build a vector store instance based on user's KB configuration from database.

    Args:
        kb_path: Path to the knowledge base directory
        collection_name: Name of the collection/index
        embedding_function: Embedding function to use
        user_id: User ID for configuration lookup
        session: Database session

    Returns:
        Vector store adapter instance

    Raises:
        ValueError: If provider is not supported
        ImportError: If required dependencies are not available
    """
    variable_service = get_variable_service()

    # Get user's KB configuration variables
    kb_vars = await variable_service.get_by_category(user_id, "KB", session)

    # Convert variables to config dict
    config = {var.name: var.value for var in kb_vars}

    # Default to Chroma if no provider configured
    provider = config.get("kb_provider", "chroma").lower()

    if provider == "chroma":
        return await _build_chroma_store(kb_path, collection_name, embedding_function, config)
    if provider == "opensearch":
        return _build_opensearch_store(kb_path, collection_name, embedding_function, config)
    error_msg = f"Unsupported vector store provider: {provider}"
    raise ValueError(error_msg)


async def _build_chroma_store(
    kb_path: Path,
    collection_name: str,
    embedding_function: Any | None,
    config: dict[str, Any],
) -> ChromaVectorStoreAdapter:
    """Build a Chroma vector store instance."""
    try:
        from langchain_chroma import Chroma
    except ImportError as e:
        msg = "Could not import Chroma integration package. Please install it with `pip install langchain-chroma`."
        raise ImportError(msg) from e

    # Resolve Chroma-specific parameters
    persist_directory = config.get("kb_chroma_persist_directory", str(kb_path))

    # Handle server-based Chroma
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
        # Default to local Chroma
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
    embedding_function: Any | None,
    config: dict[str, Any],
) -> MockOpenSearchVectorStore:
    """Build an OpenSearch vector store instance."""
    # For now, use the mock implementation until the real component is ready
    # TODO: Replace with actual OpenSearch component when available

    opensearch_url = config.get("kb_opensearch_url")
    index_prefix = config.get("kb_opensearch_index_prefix", "kb-")
    index_name = f"{index_prefix}{collection_name}"

    return MockOpenSearchVectorStore(
        embedding_function=embedding_function,
        opensearch_url=opensearch_url,
        index_name=index_name,
    )

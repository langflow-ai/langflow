"""Provider-aware metadata adapters for Knowledge Bases.

This module provides a unified interface for extracting metadata from different
vector store backends, making metadata operations provider-agnostic.
"""
# ruff: noqa: BLE001, G004, ARG002, TRY401

from __future__ import annotations

import contextlib
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from langflow.base.knowledge_bases.vector_store_factory import VectorStoreProtocol

logger = logging.getLogger(__name__)


class MetadataAdapter(ABC):
    """Abstract base class for vector store metadata adapters."""

    def __init__(self, vector_store: VectorStoreProtocol, kb_path: Path):
        """Initialize the metadata adapter.

        Args:
            vector_store: The vector store instance
            kb_path: Path to the knowledge base directory
        """
        self.vector_store = vector_store
        self.kb_path = kb_path

    @abstractmethod
    def get_documents_and_metadata(self, *, include_embeddings: bool = False) -> dict[str, Any]:
        """Get documents and metadata from the vector store.

        Args:
            include_embeddings: Whether to include embeddings in the result

        Returns:
            Dictionary containing documents, metadata, and optionally embeddings
        """

    @abstractmethod
    def get_document_count(self) -> int:
        """Get the total number of documents in the vector store.

        Returns:
            Number of documents
        """

    @abstractmethod
    def get_collection_info(self) -> dict[str, Any]:
        """Get collection/index information.

        Returns:
            Dictionary with collection metadata
        """

    @abstractmethod
    def supports_embeddings_retrieval(self) -> bool:
        """Check if this adapter supports retrieving embeddings.

        Returns:
            True if embeddings can be retrieved, False otherwise
        """

    @abstractmethod
    def get_embeddings_for_documents(self, document_ids: list[str]) -> dict[str, list[float]]:
        """Get embeddings for specific documents.

        Args:
            document_ids: List of document IDs

        Returns:
            Dictionary mapping document IDs to their embeddings
        """

    @abstractmethod
    def get_provider_specific_metadata(self) -> dict[str, Any]:
        """Get provider-specific metadata.

        Returns:
            Dictionary with provider-specific information
        """


class ChromaMetadataAdapter(MetadataAdapter):
    """Metadata adapter for Chroma vector stores."""

    def get_documents_and_metadata(self, *, include_embeddings: bool = False) -> dict[str, Any]:
        """Get documents and metadata from Chroma."""
        try:
            include_list = ["documents", "metadatas"]
            if include_embeddings and self.supports_embeddings_retrieval():
                include_list.append("embeddings")

            return self.vector_store.get(include=include_list)
        except (AttributeError, KeyError, ValueError) as e:
            logger.warning("Error getting documents from Chroma: %s", e)
            return {"documents": [], "metadatas": [], "embeddings": [] if include_embeddings else None}

    def get_document_count(self) -> int:
        """Get document count from Chroma."""
        try:
            if hasattr(self.vector_store, "_collection") and self.vector_store._collection:
                return self.vector_store._collection.count()
            # Fallback: get all documents and count
            result = self.vector_store.get()
            return len(result.get("documents", []))
        except Exception as e:
            logger.warning("Error getting document count from Chroma: %s", e)
            return 0

    def get_collection_info(self) -> dict[str, Any]:
        """Get Chroma collection information."""
        info = {}
        try:
            if hasattr(self.vector_store, "_collection") and self.vector_store._collection:
                collection = self.vector_store._collection
                info["name"] = collection.name
                info["count"] = collection.count()

                # Try to get metadata if available
                import contextlib

                with contextlib.suppress(Exception):
                    info["metadata"] = collection.metadata

        except Exception as e:
            logger.warning("Error getting Chroma collection info: %s", e)

        return info

    def supports_embeddings_retrieval(self) -> bool:
        """Chroma supports embeddings retrieval through its collection interface."""
        return hasattr(self.vector_store, "_collection") and self.vector_store._collection is not None

    def get_embeddings_for_documents(self, document_ids: list[str]) -> dict[str, list[float]]:
        """Get embeddings for specific documents from Chroma."""
        embeddings_map = {}

        if not self.supports_embeddings_retrieval():
            return embeddings_map

        try:
            collection = self.vector_store._collection
            result = collection.get(where={"_id": {"$in": document_ids}}, include=["metadatas", "embeddings"])

            metadatas = result.get("metadatas", [])
            embeddings = result.get("embeddings", [])

            for i, metadata in enumerate(metadatas):
                if metadata and "_id" in metadata and i < len(embeddings):
                    embeddings_map[metadata["_id"]] = embeddings[i]

        except Exception as e:
            logger.warning("Error getting embeddings from Chroma: %s", e)

        return embeddings_map

    def get_provider_specific_metadata(self) -> dict[str, Any]:
        """Get Chroma-specific metadata."""
        metadata = {"provider": "chroma"}

        try:
            if hasattr(self.vector_store, "_client") and self.vector_store._client:
                # Try to get client information
                client = self.vector_store._client
                metadata["client_type"] = type(client).__name__

                # Try to get version if available
                with contextlib.suppress(Exception):
                    metadata["version"] = client.get_version()

        except Exception as e:
            logger.warning(f"Error getting Chroma-specific metadata: {e}")

        return metadata


class OpenSearchMetadataAdapter(MetadataAdapter):
    """Metadata adapter for OpenSearch vector stores (including mock)."""

    def get_documents_and_metadata(self, *, include_embeddings: bool = False) -> dict[str, Any]:
        """Get documents and metadata from OpenSearch."""
        try:
            include_list = ["documents", "metadatas"]
            if include_embeddings:
                include_list.append("embeddings")

            return self.vector_store.get(include=include_list)
        except Exception as e:
            logger.warning(f"Error getting documents from OpenSearch: {e}")
            return {"documents": [], "metadatas": [], "embeddings": [] if include_embeddings else None}

    def get_document_count(self) -> int:
        """Get document count from OpenSearch."""
        try:
            # For mock implementation, count documents directly
            if hasattr(self.vector_store, "_documents"):
                return len(self.vector_store._documents)
            # For real OpenSearch, would query the index
            result = self.vector_store.get()
            return len(result.get("documents", []))
        except Exception as e:
            logger.warning(f"Error getting document count from OpenSearch: {e}")
            return 0

    def get_collection_info(self) -> dict[str, Any]:
        """Get OpenSearch index information."""
        info = {}
        try:
            if hasattr(self.vector_store, "index_name"):
                info["index_name"] = self.vector_store.index_name

            if hasattr(self.vector_store, "opensearch_url"):
                info["cluster_url"] = self.vector_store.opensearch_url

            info["document_count"] = self.get_document_count()

        except Exception as e:
            logger.warning(f"Error getting OpenSearch collection info: {e}")

        return info

    def supports_embeddings_retrieval(self) -> bool:
        """OpenSearch mock doesn't support embeddings retrieval yet."""
        # For real OpenSearch implementation, this would check if embeddings are stored
        return False

    def get_embeddings_for_documents(self, document_ids: list[str]) -> dict[str, list[float]]:
        """Get embeddings for specific documents from OpenSearch."""
        # Mock implementation doesn't support embeddings yet
        return {}

    def get_provider_specific_metadata(self) -> dict[str, Any]:
        """Get OpenSearch-specific metadata."""
        metadata = {"provider": "opensearch"}

        try:
            # Add OpenSearch cluster and index information
            if hasattr(self.vector_store, "opensearch_url"):
                metadata["cluster_url"] = self.vector_store.opensearch_url

            if hasattr(self.vector_store, "index_name"):
                metadata["index_name"] = self.vector_store.index_name

            # For real OpenSearch, we would get cluster health, version, etc.
            # metadata["cluster_health"] = client.cluster.health()
            # metadata["cluster_version"] = client.info()["version"]["number"]

        except Exception as e:
            logger.warning(f"Error getting OpenSearch-specific metadata: {e}")

        return metadata


def create_metadata_adapter(vector_store: VectorStoreProtocol, kb_path: Path) -> MetadataAdapter:
    """Create the appropriate metadata adapter for a vector store.

    Args:
        vector_store: The vector store instance (ChromaVectorStoreAdapter or MockOpenSearchVectorStore)
        kb_path: Path to the knowledge base directory

    Returns:
        Appropriate metadata adapter instance

    Raises:
        ValueError: If the vector store type is not supported
    """
    # Import here to avoid circular imports
    from pathlib import Path  # noqa: F401

    from langflow.base.knowledge_bases.vector_store_factory import ChromaVectorStoreAdapter, MockOpenSearchVectorStore

    # Direct type checking with our specific adapter types
    if isinstance(vector_store, ChromaVectorStoreAdapter):
        return ChromaMetadataAdapter(vector_store, kb_path)
    if isinstance(vector_store, MockOpenSearchVectorStore):
        return OpenSearchMetadataAdapter(vector_store, kb_path)
    # Fallback to attribute-based detection for any other implementations
    store_type = type(vector_store).__name__.lower()
    if hasattr(vector_store, "opensearch_url") or hasattr(vector_store, "index_name"):
        logger.info(f"Detected OpenSearch-like vector store: {store_type}")
        return OpenSearchMetadataAdapter(vector_store, kb_path)
    if hasattr(vector_store, "_collection") or hasattr(vector_store, "_client"):
        logger.info(f"Detected Chroma-like vector store: {store_type}")
        return ChromaMetadataAdapter(vector_store, kb_path)
    error_msg = f"Unsupported vector store type: {store_type}"
    raise ValueError(error_msg)


def extract_metadata(
    vector_store: VectorStoreProtocol,
    kb_path: Path,
    schema_data: list[dict[str, Any]] | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    """Extract comprehensive metadata from a knowledge base using provider-aware adapters.

    Args:
        vector_store: The vector store instance
        kb_path: Path to the knowledge base directory
        schema_data: Optional schema information

    Returns:
        Dictionary containing comprehensive metadata
    """
    try:
        # Create appropriate metadata adapter
        adapter = create_metadata_adapter(vector_store, kb_path)

        # Get basic document data
        documents_data = adapter.get_documents_and_metadata(include_embeddings=False)
        documents = documents_data.get("documents", [])
        metadatas = documents_data.get("metadatas", [])

        # Calculate basic metrics
        chunk_count = len(documents)

        if chunk_count == 0:
            return {
                "chunks": 0,
                "words": 0,
                "characters": 0,
                "avg_chunk_size": 0.0,
                "embedding_provider": "Unknown",
                "embedding_model": "Unknown",
                "provider": adapter.get_provider_specific_metadata().get("provider", "unknown"),
                "collection_info": adapter.get_collection_info(),
                "provider_specific": adapter.get_provider_specific_metadata(),
                "supports_embeddings": adapter.supports_embeddings_retrieval(),
            }

        # Calculate text metrics
        total_chars = sum(len(str(doc)) for doc in documents)
        total_words = sum(len(str(doc).split()) for doc in documents)
        avg_chunk_size = total_chars / chunk_count if chunk_count > 0 else 0.0

        # Try to detect embedding info from metadata
        embedding_provider = "Unknown"
        embedding_model = "Unknown"

        if metadatas and len(metadatas) > 0:
            # Look for embedding info in first metadata entry
            first_metadata = metadatas[0] if metadatas[0] else {}
            embedding_provider = first_metadata.get("embedding_provider", "Unknown")
            embedding_model = first_metadata.get("embedding_model", "Unknown")

        # Build comprehensive metadata
        return {
            "chunks": chunk_count,
            "words": total_words,
            "characters": total_chars,
            "avg_chunk_size": avg_chunk_size,
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
            "provider": adapter.get_provider_specific_metadata().get("provider", "unknown"),
            "collection_info": adapter.get_collection_info(),
            "provider_specific": adapter.get_provider_specific_metadata(),
            "supports_embeddings": adapter.supports_embeddings_retrieval(),
        }

    except Exception as e:
        logger.exception(f"Error extracting enhanced metadata from KB '{kb_path.name}': {e}")

        # Return minimal metadata on error
        return {
            "chunks": 0,
            "words": 0,
            "characters": 0,
            "avg_chunk_size": 0.0,
            "embedding_provider": "Unknown",
            "embedding_model": "Unknown",
            "provider": "unknown",
            "collection_info": {},
            "provider_specific": {},
            "supports_embeddings": False,
        }

"""MongoDB Atlas Vector Search backend.

Wraps ``langchain_mongodb.MongoDBAtlasVectorSearch``. The connection
URI + auth tokens come from Langflow variables (same pattern as S3
and the OAuth connectors) so the ``backend_config`` dict is safe to
round-trip through the UI — it carries variable *names*, never raw
secrets.

``backend_config`` shape::

    {
        "connection_uri_variable": "MONGODB_ATLAS_URI",
        "database": "my_db",
        "collection": "my_collection",
        "index_name": "vector_index",
        "text_key": "text",           # optional, default "text"
        "embedding_key": "embedding", # optional, default "embedding"
    }

``langchain_mongodb`` is optional. The backend imports it lazily so
Langflow installs without MongoDB-specific deps keep working; a
``MissingOptionalDependencyError`` surfaces the moment someone
selects this backend without installing the extra.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.backends.base import (
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
)
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langchain_core.vectorstores import VectorStore


DEFAULT_CONNECTION_URI_VARIABLE = "MONGODB_ATLAS_URI"
DEFAULT_TEXT_KEY = "text"
DEFAULT_EMBEDDING_KEY = "embedding"
DEFAULT_INDEX_NAME = "vector_index"


class MongoDBBackend(BaseVectorStoreBackend):
    """MongoDB Atlas Vector Search as a Langflow KB backend."""

    backend_type = BackendType.MONGODB

    def _required(self, key: str) -> str:
        value = self.backend_config.get(key)
        if not value:
            msg = f"MongoDBBackend requires '{key}' in backend_config."
            raise ValueError(msg)
        return str(value)

    def _resolve_connection_uri(self) -> str:
        variable_name = self.backend_config.get("connection_uri_variable") or DEFAULT_CONNECTION_URI_VARIABLE
        value = os.environ.get(variable_name)
        if not value:
            msg = (
                f"MongoDBBackend needs the '{variable_name}' Langflow variable "
                "(or env var of the same name) populated with the Atlas URI."
            )
            raise ValueError(msg)
        return value

    def _build_vector_store(self) -> VectorStore:
        # Validate config before touching optional deps so missing
        # fields surface as a clean ``ValueError`` regardless of
        # whether the langchain-mongodb extras are installed.
        database = self._required("database")
        collection_name = self._required("collection")
        uri = self._resolve_connection_uri()
        index_name = self.backend_config.get("index_name") or DEFAULT_INDEX_NAME
        text_key = self.backend_config.get("text_key") or DEFAULT_TEXT_KEY
        embedding_key = self.backend_config.get("embedding_key") or DEFAULT_EMBEDDING_KEY

        try:
            from langchain_mongodb import MongoDBAtlasVectorSearch
            from pymongo import MongoClient
        except ImportError as exc:
            msg = (
                "MongoDBBackend requires langchain-mongodb and pymongo. "
                "Install the 'mongodb' extras or add those packages."
            )
            raise RuntimeError(msg) from exc

        client = MongoClient(uri)
        collection = client[database][collection_name]
        # Stash so ``teardown`` can close the client cleanly.
        self._mongo_client = client
        return MongoDBAtlasVectorSearch(
            collection=collection,
            embedding=self.embedding_function,
            index_name=index_name,
            text_key=text_key,
            embedding_key=embedding_key,
        )

    async def count(self) -> int:
        # MongoDB collections expose ``estimated_document_count`` for
        # cheap counts; fall back to ``count_documents`` if the driver
        # doesn't surface it.
        client = getattr(self, "_mongo_client", None)
        if client is None:
            # Force a build so the collection is accessible.
            _ = self.vector_store
            client = self._mongo_client
        try:
            collection = client[self._required("database")][self._required("collection")]
            return int(collection.estimated_document_count())
        except Exception as exc:  # noqa: BLE001
            logger.debug("MongoDB count() failed for %s: %s", self.kb_name, exc)
            return 0

    async def iter_documents(
        self,
        *,
        batch_size: int = 5000,
        include_embeddings: bool = False,
    ) -> AsyncIterator[list[IngestedDocument]]:
        """Paginate the collection via MongoDB's cursor."""
        client = getattr(self, "_mongo_client", None)
        if client is None:
            _ = self.vector_store
            client = self._mongo_client

        collection = client[self._required("database")][self._required("collection")]
        text_key = self.backend_config.get("text_key") or DEFAULT_TEXT_KEY
        embedding_key = self.backend_config.get("embedding_key") or DEFAULT_EMBEDDING_KEY

        projection: dict[str, Any] = {text_key: 1, "metadata": 1, "source_metadata": 1}
        if include_embeddings:
            projection[embedding_key] = 1

        batch: list[IngestedDocument] = []
        for raw in collection.find({}, projection=projection):
            content = raw.get(text_key) or ""
            metadata = raw.get("metadata") or {
                k: v for k, v in raw.items() if k not in {text_key, embedding_key, "_id", "metadata"}
            }
            embedding = raw.get(embedding_key) if include_embeddings else None
            batch.append(
                IngestedDocument(
                    content=str(content),
                    metadata=dict(metadata) if isinstance(metadata, dict) else {},
                    embedding=list(embedding) if embedding else None,
                )
            )
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    async def storage_size_bytes(self) -> int:
        client = getattr(self, "_mongo_client", None)
        if client is None:
            return 0
        try:
            stats = client[self._required("database")].command({"collStats": self._required("collection")})
            return int(stats.get("size") or 0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("MongoDB collStats failed for %s: %s", self.kb_name, exc)
            return 0

    async def teardown(self) -> None:
        client = getattr(self, "_mongo_client", None)
        if client is not None:
            try:
                client.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("MongoClient.close failed: %s", exc)
        self._mongo_client = None
        self._vector_store = None

    async def delete_collection(self) -> None:
        """Drop the configured collection. Used by KB deletion."""
        client = getattr(self, "_mongo_client", None)
        if client is None:
            _ = self.vector_store
            client = self._mongo_client
        try:
            client[self._required("database")].drop_collection(self._required("collection"))
        except Exception as exc:  # noqa: BLE001
            logger.debug("MongoDB drop_collection failed: %s", exc)

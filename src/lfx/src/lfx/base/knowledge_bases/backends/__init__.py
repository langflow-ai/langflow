"""Vector-store backend abstraction for Knowledge Bases.

Provides a thin wrapper over LangChain's ``VectorStore`` base so Langflow's KB
subsystem can address multiple vector databases (Chroma today; MongoDB, Astra,
Postgres in later phases) through a single interface.

Public surface:

* ``VectorStoreBackend`` — the protocol KB helpers depend on.
* ``BaseVectorStoreBackend`` — default implementation wrapping a LangChain
  ``VectorStore`` instance; subclasses override only what's backend-specific.
* ``BackendType`` — enum of registered backend identifiers.
* ``register_backend`` / ``create_backend`` — registry entry points.

Chroma is registered on import so existing call sites keep working.
"""

from lfx.base.knowledge_bases.backends.astra import AstraBackend
from lfx.base.knowledge_bases.backends.base import (
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
    VectorStoreBackend,
)
from lfx.base.knowledge_bases.backends.chroma import ChromaBackend
from lfx.base.knowledge_bases.backends.mongodb import MongoDBBackend
from lfx.base.knowledge_bases.backends.opensearch import OpenSearchBackend
from lfx.base.knowledge_bases.backends.postgres import PostgresBackend
from lfx.base.knowledge_bases.backends.registry import (
    create_backend,
    get_backend_class,
    register_backend,
    registered_backends,
)

# Register built-in backends on import.
register_backend(BackendType.CHROMA, ChromaBackend)
register_backend(BackendType.MONGODB, MongoDBBackend)
register_backend(BackendType.ASTRA, AstraBackend)
register_backend(BackendType.POSTGRES, PostgresBackend)
register_backend(BackendType.OPENSEARCH, OpenSearchBackend)

__all__ = [
    "AstraBackend",
    "BackendType",
    "BaseVectorStoreBackend",
    "ChromaBackend",
    "IngestedDocument",
    "MongoDBBackend",
    "OpenSearchBackend",
    "PostgresBackend",
    "VectorStoreBackend",
    "create_backend",
    "get_backend_class",
    "register_backend",
    "registered_backends",
]

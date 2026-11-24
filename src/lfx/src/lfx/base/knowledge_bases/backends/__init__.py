"""Knowledge Base backends. SQLite, OpenSearch and Postgres are supported.

Chroma class names remain importable as migration-required compatibility stubs.
SQLite is the local default, with pgVector taking precedence when configured.
"""

from importlib import import_module
from typing import Any

from lfx.base.knowledge_bases.backends.base import (
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
    TestConnectionResult,
)
from lfx.base.knowledge_bases.backends.registry import (
    create_backend,
    get_backend_class,
    is_local_backend,
    is_local_chroma,
    register_backend,
    registered_backends,
)

# Register the supported built-in backends on import. AstraBackend /
# MongoDBBackend are intentionally NOT registered while they're stubbed out —
# see each module's docstring.
#
# PostgresBackend is environment-driven: it snap-configures from
# PGVECTOR_CONNECTION_STRING and needs no per-KB backend_config, so it is
# registered unconditionally. The lazy langchain-postgres import surfaces a
# clear install hint if the optional extra is missing.
# Built-ins are registered lazily in registry.py. Introspection and use of a
# different backend must not require Chroma or any other provider's SDK.
_LAZY_EXPORTS = {
    "AstraBackend": "astra",
    "ChromaBackend": "chroma",
    "ChromaCloudBackend": "chroma",
    "ChromaLocalBackend": "chroma",
    "MongoDBBackend": "mongodb",
    "OpenSearchBackend": "opensearch",
    "PostgresBackend": "postgres",
    "SQLiteBackend": "sqlite",
    "SQLiteStorageContext": "sqlite",
}


def __getattr__(name: str) -> Any:
    """Load provider backend classes lazily without importing optional SDKs at package import."""
    if name not in _LAZY_EXPORTS:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    value = getattr(import_module(f"{__name__}.{_LAZY_EXPORTS[name]}"), name)
    globals()[name] = value
    return value


__all__ = [
    "AstraBackend",
    "BackendType",
    "BaseVectorStoreBackend",
    "ChromaBackend",
    "ChromaCloudBackend",
    "ChromaLocalBackend",
    "IngestedDocument",
    "MongoDBBackend",
    "OpenSearchBackend",
    "PostgresBackend",
    "SQLiteBackend",
    "SQLiteStorageContext",
    "TestConnectionResult",
    "create_backend",
    "get_backend_class",
    "is_local_backend",
    "is_local_chroma",
    "register_backend",
    "registered_backends",
]

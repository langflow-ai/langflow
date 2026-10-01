"""Vector-store backend abstraction for Knowledge Bases.

Provides a thin wrapper over LangChain's ``VectorStore`` base so Langflow's KB
subsystem can address multiple vector databases through a single interface.

Public surface:

* ``BaseVectorStoreBackend`` — abstract base class every backend inherits
  from; wraps a LangChain ``VectorStore`` so subclasses override only
  what's backend-specific.
* ``BackendType`` — enum of registered backend identifiers.
* ``register_backend`` / ``create_backend`` — registry entry points.

**SQLite**, **Chroma**, **OpenSearch**, and **Postgres (pgvector)** are registered
lazily. SQLite requires the native ``lfx[sqlite]`` extra and explicit trusted
storage context. The application's default switch is a separate upgrade gate. The
``AstraBackend`` / ``MongoDBBackend`` classes are preserved as stubs so the
framework wiring (enum values, type imports, DB-stored ``backend_type`` strings
on existing rows) keeps round-tripping, but they are not instantiable through
``create_backend`` and the picker UI hides them. Reinstate by re-introducing the
full implementation and re-adding ``register_backend(...)`` for that backend below.

Postgres is environment-driven — it snap-configures from
``PGVECTOR_CONNECTION_STRING`` and becomes the default backend when that env var
is present (see ``postgres.py``).

Chroma ships as two concrete classes:
* ``ChromaLocalBackend`` — local ``PersistentClient``; registered under
  ``BackendType.CHROMA``.
* ``ChromaCloudBackend`` — ``CloudClient``; resolved at factory time by
  ``create_backend`` inspecting ``backend_config["mode"]``.

``ChromaBackend`` is kept as a backward-compat alias for ``ChromaLocalBackend``.
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
# ChromaCloudBackend shares BackendType.CHROMA; create_backend() dispatches
# to the correct class based on backend_config["mode"] at call time.
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

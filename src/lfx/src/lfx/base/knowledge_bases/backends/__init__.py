"""Vector-store backend abstraction for Knowledge Bases.

Provides a thin wrapper over LangChain's ``VectorStore`` base so Langflow's KB
subsystem can address multiple vector databases through a single interface.

Public surface:

* ``BaseVectorStoreBackend`` — abstract base class every backend inherits
  from; wraps a LangChain ``VectorStore`` so subclasses override only
  what's backend-specific.
* ``BackendType`` — enum of registered backend identifiers.
* ``register_backend`` / ``create_backend`` — registry entry points.

In this phase only **Chroma** and **OpenSearch** are registered. The
``AstraBackend`` / ``MongoDBBackend`` / ``PostgresBackend`` classes are
preserved as stubs so the framework wiring (enum values, type imports,
DB-stored ``backend_type`` strings on existing rows) keeps round-tripping,
but they are not instantiable through ``create_backend`` and the picker UI
hides them. Reinstate by re-introducing the full implementation and
re-adding ``register_backend(...)`` for that backend below.

Chroma ships as two concrete classes:
* ``ChromaLocalBackend`` — local ``PersistentClient``; registered under
  ``BackendType.CHROMA``.
* ``ChromaCloudBackend`` — ``CloudClient``; resolved at factory time by
  ``create_backend`` inspecting ``backend_config["mode"]``.

``ChromaBackend`` is kept as a backward-compat alias for ``ChromaLocalBackend``.
"""

from lfx.base.knowledge_bases.backends.astra import AstraBackend
from lfx.base.knowledge_bases.backends.base import (
    BackendType,
    BaseVectorStoreBackend,
    IngestedDocument,
    TestConnectionResult,
)
from lfx.base.knowledge_bases.backends.chroma import (
    ChromaBackend,
    ChromaCloudBackend,
    ChromaLocalBackend,
)
from lfx.base.knowledge_bases.backends.mongodb import MongoDBBackend
from lfx.base.knowledge_bases.backends.opensearch import OpenSearchBackend
from lfx.base.knowledge_bases.backends.postgres import PostgresBackend
from lfx.base.knowledge_bases.backends.registry import (
    create_backend,
    get_backend_class,
    register_backend,
    registered_backends,
)

# Register the supported built-in backends on import. AstraBackend /
# MongoDBBackend / PostgresBackend are intentionally NOT registered while
# they're stubbed out — see each module's docstring.
#
# ChromaCloudBackend shares BackendType.CHROMA; create_backend() dispatches
# to the correct class based on backend_config["mode"] at call time.
register_backend(BackendType.CHROMA, ChromaLocalBackend)
register_backend(BackendType.OPENSEARCH, OpenSearchBackend)

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
    "TestConnectionResult",
    "create_backend",
    "get_backend_class",
    "register_backend",
    "registered_backends",
]

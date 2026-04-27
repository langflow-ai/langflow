"""Postgres (pgvector) vector-store backend — stub.

The full implementation has been removed for this phase. Only Chroma and
OpenSearch are supported; the ``BackendType.POSTGRES`` enum value is
kept so existing DB rows referencing it round-trip safely, but the
class is not registered with
:func:`lfx.base.knowledge_bases.backends.create_backend` and
instantiating / using it raises ``NotImplementedError``.

When pgvector support is reinstated, restore the full backend
(connection-URL variable resolution, collection-name handling, async
``iter_documents``) and re-register it in ``backends/__init__.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.base.knowledge_bases.backends.base import BackendType, BaseVectorStoreBackend

if TYPE_CHECKING:
    from langchain_core.vectorstores import VectorStore


_DISABLED_MESSAGE = (
    "Postgres (pgvector) knowledge-base backend is not available in this build. Use Chroma or OpenSearch instead."
)


class PostgresBackend(BaseVectorStoreBackend):
    """Stub kept for type-and-enum compatibility only.

    The backend is intentionally not registered. ``create_backend('postgres')``
    will raise ``ValueError`` from the registry; if a caller bypasses the
    registry and instantiates this class directly, ``_build_vector_store``
    raises ``NotImplementedError``.
    """

    backend_type = BackendType.POSTGRES

    def _build_vector_store(self) -> VectorStore:
        raise NotImplementedError(_DISABLED_MESSAGE)

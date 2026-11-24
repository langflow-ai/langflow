"""Import-safe compatibility names for Chroma stores retired in 1.13.

The one-time upgrade helper is the only supported reader of legacy data.
Constructing these classes never opens a source store or creates a target.
"""

from typing import Any

from langchain_core.vectorstores import VectorStore

from lfx.base.knowledge_bases.backends.base import BackendType, BaseVectorStoreBackend


class ChromaMigrationRequiredError(RuntimeError):
    """Legacy routing cannot be served by the Chroma-free runtime."""

    def __init__(self) -> None:
        """Describe the supported migration path while preserving original Chroma data."""
        super().__init__(
            "Chroma support was retired in Langflow 1.13. This store requires migration. "
            "For a local Knowledge Base, check the automatic upgrade migration status. "
            "For a standalone Chroma/Local DB node or Chroma Cloud store, migrate its data "
            "to a supported Knowledge Base and reconnect the flow. Original data is retained. "
            "Installing a Chroma package does not enable this retired integration."
        )


class ChromaLocalBackend(BaseVectorStoreBackend):
    """Retain the historical class identity without a live SDK dependency."""

    backend_type = BackendType.CHROMA

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        """Reject retired Chroma construction before touching storage or credentials."""
        raise ChromaMigrationRequiredError

    def _build_vector_store(self) -> VectorStore:
        """Reject creation of a vector store through a retired Chroma backend."""
        raise ChromaMigrationRequiredError


class ChromaCloudBackend(ChromaLocalBackend):
    """Retired remote Chroma routing. Never reinterpret it as local storage."""


ChromaBackend = ChromaLocalBackend


def build_default_chroma_backend(*_args: Any, **_kwargs: Any) -> ChromaLocalBackend:
    """Historical entry point retained only to give an actionable error."""
    raise ChromaMigrationRequiredError

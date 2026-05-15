"""lfx-qdrant: Qdrant bundle.

Distribution unit ``lfx-qdrant``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:qdrant:<Class>@official``.
"""

from lfx_qdrant.components.qdrant.qdrant import QdrantVectorStoreComponent

__all__ = [
    "QdrantVectorStoreComponent",
]

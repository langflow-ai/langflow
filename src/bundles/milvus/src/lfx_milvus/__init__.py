"""lfx-milvus: Milvus bundle.

Distribution unit ``lfx-milvus``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:milvus:<Class>@official``.
"""

from lfx_milvus.components.milvus.milvus import MilvusVectorStoreComponent

__all__ = [
    "MilvusVectorStoreComponent",
]

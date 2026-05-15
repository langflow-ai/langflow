"""lfx-weaviate: Weaviate bundle.

Distribution unit ``lfx-weaviate``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:weaviate:<Class>@official``.
"""

from lfx_weaviate.components.weaviate.weaviate import WeaviateVectorStoreComponent

__all__ = [
    "WeaviateVectorStoreComponent",
]

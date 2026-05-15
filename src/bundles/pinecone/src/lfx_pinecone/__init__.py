"""lfx-pinecone: Pinecone bundle.

Distribution unit ``lfx-pinecone``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:pinecone:<Class>@official``.
"""

from lfx_pinecone.components.pinecone.pinecone import PineconeVectorStoreComponent

__all__ = [
    "PineconeVectorStoreComponent",
]

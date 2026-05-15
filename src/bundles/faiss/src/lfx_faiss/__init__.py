"""lfx-faiss: Faiss bundle.

Distribution unit ``lfx-faiss``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:faiss:<Class>@official``.
"""

from lfx_faiss.components.faiss.faiss import FaissVectorStoreComponent

__all__ = [
    "FaissVectorStoreComponent",
]

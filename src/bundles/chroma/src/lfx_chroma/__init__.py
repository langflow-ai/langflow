"""lfx-chroma: Chroma bundle.

Distribution unit ``lfx-chroma``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:chroma:<Class>@official``.
"""

from lfx_chroma.components.chroma.chroma import ChromaVectorStoreComponent

__all__ = [
    "ChromaVectorStoreComponent",
]

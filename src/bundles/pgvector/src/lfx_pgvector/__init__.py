"""lfx-pgvector: Pgvector bundle.

Distribution unit ``lfx-pgvector``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:pgvector:<Class>@official``.
"""

from lfx_pgvector.components.pgvector.pgvector import PGVectorStoreComponent

__all__ = [
    "PGVectorStoreComponent",
]

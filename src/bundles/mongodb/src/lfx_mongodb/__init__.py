"""lfx-mongodb: Mongodb bundle.

Distribution unit ``lfx-mongodb``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:mongodb:<Class>@official``.
"""

from lfx_mongodb.components.mongodb.mongodb_atlas import MongoVectorStoreComponent

__all__ = [
    "MongoVectorStoreComponent",
]

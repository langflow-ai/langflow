"""lfx-couchbase: Couchbase bundle.

Distribution unit ``lfx-couchbase``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:couchbase:<Class>@official``.
"""

from lfx_couchbase.components.couchbase.couchbase import CouchbaseVectorStoreComponent

__all__ = [
    "CouchbaseVectorStoreComponent",
]

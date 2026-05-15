"""lfx-upstash: Upstash bundle.

Distribution unit ``lfx-upstash``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:upstash:<Class>@official``.
"""

from lfx_upstash.components.upstash.upstash import UpstashVectorStoreComponent

__all__ = [
    "UpstashVectorStoreComponent",
]

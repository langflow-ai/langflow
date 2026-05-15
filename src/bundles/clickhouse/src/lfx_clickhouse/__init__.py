"""lfx-clickhouse: Clickhouse bundle.

Distribution unit ``lfx-clickhouse``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:clickhouse:<Class>@official``.
"""

from lfx_clickhouse.components.clickhouse.clickhouse import ClickhouseVectorStoreComponent

__all__ = [
    "ClickhouseVectorStoreComponent",
]

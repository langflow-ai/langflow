"""lfx-agentics: Agentics bundle.

Distribution unit ``lfx-agentics``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:agentics:<Class>@official``.
"""

from lfx_agentics.components.agentics.agenerate_component import AgenerateComponent
from lfx_agentics.components.agentics.amap_component import AMapComponent
from lfx_agentics.components.agentics.areduce_component import AreduceComponent

__all__ = [
    "AMapComponent",
    "AgenerateComponent",
    "AreduceComponent",
]

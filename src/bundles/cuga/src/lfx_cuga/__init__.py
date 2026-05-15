"""lfx-cuga: Cuga bundle.

Distribution unit ``lfx-cuga``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:cuga:<Class>@official``.
"""

from lfx_cuga.components.cuga.cuga_agent import CugaComponent

__all__ = [
    "CugaComponent",
]

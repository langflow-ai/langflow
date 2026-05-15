"""lfx-altk: Altk bundle.

Distribution unit ``lfx-altk``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:altk:<Class>@official``.
"""

from lfx_altk.components.altk.altk_agent import ALTKAgentComponent

__all__ = [
    "ALTKAgentComponent",
]

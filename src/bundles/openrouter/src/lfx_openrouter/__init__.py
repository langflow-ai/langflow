"""lfx-openrouter: Openrouter bundle.

Distribution unit ``lfx-openrouter``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:openrouter:<Class>@official``.
"""

from lfx_openrouter.components.openrouter.openrouter import OpenRouterComponent

__all__ = [
    "OpenRouterComponent",
]

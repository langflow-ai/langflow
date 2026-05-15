"""lfx-sambanova: Sambanova bundle.

Distribution unit ``lfx-sambanova``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:sambanova:<Class>@official``.
"""

from lfx_sambanova.components.sambanova.sambanova import SambaNovaComponent

__all__ = [
    "SambaNovaComponent",
]

"""lfx-olivya: Olivya bundle.

Distribution unit ``lfx-olivya``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:olivya:<Class>@official``.
"""

from lfx_olivya.components.olivya.olivya import OlivyaComponent

__all__ = [
    "OlivyaComponent",
]

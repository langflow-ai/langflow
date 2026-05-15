"""lfx-needle: Needle bundle.

Distribution unit ``lfx-needle``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:needle:<Class>@official``.
"""

from lfx_needle.components.needle.needle import NeedleComponent

__all__ = [
    "NeedleComponent",
]

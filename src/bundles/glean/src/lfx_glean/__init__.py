"""lfx-glean: Glean bundle.

Distribution unit ``lfx-glean``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:glean:<Class>@official``.
"""

from lfx_glean.components.glean.glean_search_api import GleanSearchAPIComponent

__all__ = [
    "GleanSearchAPIComponent",
]

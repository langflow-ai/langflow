"""lfx-bing: Bing bundle.

Distribution unit ``lfx-bing``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:bing:<Class>@official``.
"""

from lfx_bing.components.bing.bing_search_api import BingSearchAPIComponent

__all__ = [
    "BingSearchAPIComponent",
]

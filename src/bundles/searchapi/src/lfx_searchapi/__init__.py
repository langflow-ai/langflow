"""lfx-searchapi: Searchapi bundle.

Distribution unit ``lfx-searchapi``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:searchapi:<Class>@official``.
"""

from lfx_searchapi.components.searchapi.search import SearchComponent

__all__ = [
    "SearchComponent",
]

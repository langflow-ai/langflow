"""lfx-contextfetch: ContextFetch web search and page contents bundle.

This package is the distribution unit ``lfx-contextfetch``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers ``ContextFetchSearchComponent`` and
``ContextFetchContentsComponent`` under the namespaced IDs
``ext:contextfetch:<ClassName>@official``.

ContextFetch (https://contextfetch.dev) is a web search and page contents API;
the components call it directly with ``httpx`` and need only a user-supplied
API key, so the bundle carries no vendor SDK dependency.
"""

from lfx_contextfetch.components.contextfetch.contextfetch_contents import ContextFetchContentsComponent
from lfx_contextfetch.components.contextfetch.contextfetch_search import ContextFetchSearchComponent

__all__ = ["ContextFetchContentsComponent", "ContextFetchSearchComponent"]

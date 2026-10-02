"""lfx-linkup: Linkup Search and Linkup Fetch bundle.

This package is the distribution unit ``lfx-linkup``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers ``LinkupSearchComponent`` and
``LinkupFetchComponent`` under the namespaced IDs
``ext:linkup:LinkupSearchComponent@official`` and
``ext:linkup:LinkupFetchComponent@official``.

Linkup (https://www.linkup.so) is a web search API for AI applications;
both components are built on the official ``linkup-sdk`` client.
"""

from lfx_linkup.components.linkup.linkup_fetch import LinkupFetchComponent
from lfx_linkup.components.linkup.linkup_search import LinkupSearchComponent

__all__ = ["LinkupFetchComponent", "LinkupSearchComponent"]

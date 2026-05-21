"""lfx-duckduckgo: DuckDuckGo Search bundle.

This package is the distribution unit ``lfx-duckduckgo``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers ``DuckDuckGoSearchComponent`` under the
namespaced ID ``ext:duckduckgo:DuckDuckGoSearchComponent@official``.

The first provider extracted from ``lfx.components.<provider>`` into
a standalone Bundle.
"""

from lfx_duckduckgo.components.duckduckgo.duck_duck_go_search_run import (
    DuckDuckGoSearchComponent,
)

__all__ = ["DuckDuckGoSearchComponent"]

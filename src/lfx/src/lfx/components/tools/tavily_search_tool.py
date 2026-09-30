# lfx-compat-shim
"""Compatibility alias for the Tavily search component now shipped by lfx-bundles.

The old Tools-category implementation is intentionally no longer registered as
a core palette component. Keep the import path alive so older code that imports
``lfx.components.tools.tavily_search_tool.TavilySearchToolComponent`` resolves to
the maintained Tavily bundle component.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.components.tavily import TavilySearchComponent as TavilySearchToolComponent

__all__ = ["TavilySearchToolComponent"]


def __getattr__(attr_name: str) -> Any:
    if attr_name != "TavilySearchToolComponent":
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)

    from lfx.components.tavily import TavilySearchComponent

    globals()[attr_name] = TavilySearchComponent
    return TavilySearchComponent

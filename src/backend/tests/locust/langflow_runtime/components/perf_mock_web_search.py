"""Stub web search for Natural ``external_apis=stubbed`` (keeps ``UnifiedWebSearch`` type)."""

from __future__ import annotations

import pandas as pd
from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema import DataFrame

PERF_MOCK_WEB_SEARCH_MARKER = "PERF_MOCK_WEB_SEARCH"


class WebSearchComponent(Component):
    """Deterministic web-search tool — no DuckDuckGo/Google HTTP."""

    display_name = "Web Search"
    description = "Stub web search for Natural suite stubbed runs."
    name = "UnifiedWebSearch"
    icon = "search"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="Echoed into the stub snippet.",
            tool_mode=True,
            required=True,
            value="perf-natural",
        ),
    ]
    outputs = [Output(name="results", display_name="Results", method="perform_search")]

    def perform_search(self) -> DataFrame:
        query = getattr(self.query, "text", None) or str(self.query or "")
        return DataFrame(
            pd.DataFrame(
                [
                    {
                        "title": PERF_MOCK_WEB_SEARCH_MARKER,
                        "link": "https://example.invalid/perf-natural-search",
                        "snippet": f"{PERF_MOCK_WEB_SEARCH_MARKER}:{query}",
                        "content": f"{PERF_MOCK_WEB_SEARCH_MARKER}:{query}",
                    }
                ]
            )
        )

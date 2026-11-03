"""Search the web with Keenable."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.keenable.keenable_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    KeenableAPIError,
    keenable_request,
)

MAX_RESULTS_LIMIT = 50
_OPTIONAL_FILTERS = ("site", "published_after", "published_before")


class KeenableSearchComponent(Component):
    """Run a Keenable web search and return one row per result."""

    display_name = "Keenable Search"
    description = "Search the web with Keenable, a search API built for AI agents. Works without an API key."
    documentation = DOCUMENTATION_URL
    icon = "Keenable"
    name = "KeenableSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Keenable API Key",
            info=API_KEY_INFO,
            required=False,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The query to search the web for.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info=f"The number of results to return, from 1 to {MAX_RESULTS_LIMIT}.",
            value=5,
            advanced=True,
        ),
        MessageTextInput(
            name="site",
            display_name="Site",
            info="Only return results from this domain, such as docs.python.org.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="published_after",
            display_name="Published After",
            info="Only return pages published on or after this date (YYYY-MM-DD).",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="published_before",
            display_name="Published Before",
            info="Only return pages published on or before this date (YYYY-MM-DD).",
            advanced=True,
            tool_mode=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Keenable to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="search_dataframe"),
    ]

    def search(self) -> list[Data]:
        """Return one ``Data`` per result, with the page text as ``text``."""
        query = str(self.query or "").strip()
        if not query:
            error = "Enter a search query."
            self.status = error
            return [Data(text=error, data={"error": error})]

        max_results = min(max(int(self.max_results or 1), 1), MAX_RESULTS_LIMIT)
        payload: dict[str, object] = {"query": query, "max_results": max_results}
        for field in _OPTIONAL_FILTERS:
            value = str(getattr(self, field, None) or "").strip()
            if value:
                payload[field] = value

        try:
            body = keenable_request(
                "POST",
                "/v1/search/public",
                "/v1/search",
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                json=payload,
            )
            results = body.get("results")
            if not isinstance(results, list):
                msg = "Keenable API returned a search response without a results list."
                raise KeenableAPIError(msg)
        except KeenableAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        # ``snippet`` carries the page text; ``description`` is usually empty.
        data = [
            Data(
                text=str(item.get("snippet") or item.get("description") or item.get("title") or ""),
                data=item,
            )
            for item in results
            if isinstance(item, dict)
        ]
        self.status = data
        return data

    def search_dataframe(self) -> DataFrame:
        return DataFrame(self.search())

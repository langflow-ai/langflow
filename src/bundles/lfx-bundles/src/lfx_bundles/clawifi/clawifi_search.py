"""Search the web with Clawifi."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.clawifi.clawifi_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    ClawifiAPIError,
    clawifi_post,
    error_messages,
    split_list,
)

ANY_TIME = "any"
TIME_RANGES = [ANY_TIME, "day", "week", "month", "year"]


class ClawifiSearchComponent(Component):
    """Run a Clawifi web search and return one row per result."""

    display_name = "Clawifi Search"
    description = "Search the web with Clawifi, which searches many engines as one and returns one row per result."
    documentation = f"{DOCUMENTATION_URL}/api/post-search-free"
    icon = "Clawifi"
    name = "ClawifiSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Clawifi API Key",
            info=API_KEY_INFO,
            required=True,
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
            info="The number of results to return.",
            value=5,
            advanced=True,
        ),
        MessageTextInput(
            name="include_domains",
            display_name="Include Domains",
            info="Only return results from these domains, comma-separated, such as docs.python.org.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="exclude_domains",
            display_name="Exclude Domains",
            info="Never return results from these domains, comma-separated.",
            advanced=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="time_range",
            display_name="Time Range",
            info="Only return results from the last day, week, month or year.",
            options=TIME_RANGES,
            value=ANY_TIME,
            advanced=True,
            tool_mode=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Clawifi to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="search_dataframe"),
    ]

    def search(self) -> list[Data]:
        """Return one ``Data`` per result, with the result snippet as ``text``."""
        query = str(self.query or "").strip()
        if not query:
            error = "Enter a search query."
            self.status = error
            return [Data(text=error, data={"error": error})]

        payload: dict[str, object] = {"query": query, "max_results": max(int(self.max_results or 1), 1)}
        for field in ("include_domains", "exclude_domains"):
            domains = split_list(getattr(self, field, None))
            if domains:
                payload[field] = domains
        time_range = str(self.time_range or ANY_TIME).strip().lower()
        if time_range in TIME_RANGES and time_range != ANY_TIME:
            payload["time_range"] = time_range

        try:
            body = clawifi_post(
                "/search/free",
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                json=payload,
            )
            if body.get("success") is False:
                reason = error_messages(body.get("errors")) or "every search engine failed"
                msg = f"Clawifi search failed: {reason}"
                raise ClawifiAPIError(msg)
            results = body.get("results")
            if not isinstance(results, list):
                msg = "Clawifi API returned a search response without a results list."
                raise ClawifiAPIError(msg)
        except ClawifiAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        data = [
            Data(
                text=str(item.get("snippet") or item.get("title") or item.get("url") or ""),
                data={key: value for key, value in item.items() if value is not None},
            )
            for item in results
            if isinstance(item, dict)
        ]
        self.status = data
        return data

    def search_dataframe(self) -> DataFrame:
        """Return the search results as a table, one row per result."""
        return DataFrame(self.search())

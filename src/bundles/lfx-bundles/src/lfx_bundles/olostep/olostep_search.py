"""Search the web with Olostep."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.olostep.olostep_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    OlostepAPIError,
    olostep_request,
    split_list,
)

MAX_RESULTS_LIMIT = 25


class OlostepSearchComponent(Component):
    """Run an Olostep web search and return one row per result."""

    display_name = "Olostep Search"
    description = "Search the web with Olostep and optionally get each result page as markdown."
    documentation = f"{DOCUMENTATION_URL}/features/search"
    icon = "Olostep"
    name = "OlostepSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Olostep API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The query to search the web for, in natural language.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Max Results",
            info=f"The number of results to return, from 1 to {MAX_RESULTS_LIMIT}.",
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
        BoolInput(
            name="scrape_results",
            display_name="Scrape Result Pages",
            info="Also scrape each result and return its content as markdown. Each scraped page uses extra credits.",
            value=False,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Olostep to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="search_dataframe"),
    ]

    def search(self) -> list[Data]:
        """Return one ``Data`` per result, with the page markdown or description as ``text``."""
        query = str(self.query or "").strip()
        if not query:
            error = "Enter a search query."
            self.status = error
            return [Data(text=error, data={"error": error})]

        limit = min(max(int(self.limit or 1), 1), MAX_RESULTS_LIMIT)
        payload: dict[str, object] = {"query": query, "limit": limit}
        for field in ("include_domains", "exclude_domains"):
            domains = split_list(getattr(self, field, None))
            if domains:
                payload[field] = domains
        if self.scrape_results:
            payload["scrape_options"] = {"formats": ["markdown"]}

        try:
            body = olostep_request(
                "POST",
                "/v1/searches",
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                json=payload,
            )
            links = (body.get("result") or {}).get("links")
            if not isinstance(links, list):
                msg = "Olostep API returned a search response without a links list."
                raise OlostepAPIError(msg)
        except OlostepAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        data = [
            Data(
                text=str(link.get("markdown_content") or link.get("description") or link.get("title") or ""),
                data={key: value for key, value in link.items() if value is not None},
            )
            for link in links
            if isinstance(link, dict)
        ]
        self.status = data
        return data

    def search_dataframe(self) -> DataFrame:
        """Return the search results as a table, one row per result."""
        return DataFrame(self.search())

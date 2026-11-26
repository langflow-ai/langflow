"""Search the web through WebRouter."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.webrouter.webrouter_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    PROVIDER_INFO,
    WebRouterComponentError,
    call_router,
    split_list,
)

MAX_RESULTS_LIMIT = 20


class WebRouterSearchComponent(Component):
    """Run a web search through WebRouter and return one row per result."""

    display_name = "WebRouter Search"
    description = (
        "Search the web through WebRouter, which routes each call to one of several search providers "
        "and falls back to the next if it fails. Works without an API key."
    )
    documentation = DOCUMENTATION_URL
    icon = "WebRouter"
    name = "WebRouterSearch"

    inputs = [
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
            name="include_domains",
            display_name="Include Domains",
            info="Only return results from these domains, separated by commas, such as docs.python.org.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="provider",
            display_name="Provider",
            info=PROVIDER_INFO,
            advanced=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Provider API Key",
            info=API_KEY_INFO,
            required=False,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for the search, including fallbacks.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="search_dataframe"),
    ]

    def search(self) -> list[Data]:
        """Return one ``Data`` per result, with the snippet as ``text``."""
        query = str(self.query or "").strip()
        max_results = min(max(int(self.max_results or 1), 1), MAX_RESULTS_LIMIT)
        include_domains = split_list(self.include_domains) or None
        timeout = float(self.timeout or DEFAULT_TIMEOUT_SECONDS)
        try:
            if not query:
                msg = "Enter a search query."
                raise WebRouterComponentError(msg)
            response = call_router(
                self.provider,
                self.api_key,
                lambda router, provider: router.search(
                    query,
                    provider=provider,
                    max_results=max_results,
                    include_domains=include_domains,
                    timeout=timeout,
                ),
            )
        except WebRouterComponentError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        data = [
            Data(
                text=result.description or result.content or result.title or "",
                data={
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.description or result.content,
                    "published_date": result.published_date,
                    "provider": response.provider,
                },
            )
            for result in response.results
        ]
        self.status = data
        return data

    def search_dataframe(self) -> DataFrame:
        return DataFrame(self.search())

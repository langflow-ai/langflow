import importlib.metadata

import httpx

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput, StrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"
INTEGRATION_SLUG = "langflow"
DEFAULT_TIMEOUT = 90.0


def _get_integration_header() -> str:
    """Return the X-Pplx-Integration header value for outgoing requests."""
    for package in ("langflow", "langflow-base", "lfx"):
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            continue
        return f"{INTEGRATION_SLUG}/{version}"
    return f"{INTEGRATION_SLUG}/unknown"


class PerplexitySearchComponent(Component):
    display_name = "Perplexity Search API"
    description = (
        "Search the web with the Perplexity Search API. Returns ranked, "
        "LLM-friendly results with snippets, URLs, and freshness metadata."
    )
    documentation = "https://docs.perplexity.ai/api-reference/search-post"
    icon = "Perplexity"
    name = "PerplexitySearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Perplexity API Key",
            required=True,
            info="Your Perplexity API key.",
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The search query to send to Perplexity.",
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Maximum number of search results to return (1-20).",
            value=5,
        ),
        DropdownInput(
            name="search_recency_filter",
            display_name="Search Recency Filter",
            info="Restrict results to content published within the given window.",
            options=["hour", "day", "week", "month", "year"],
            value=None,
            advanced=True,
        ),
        StrInput(
            name="country",
            display_name="Country",
            info="ISO 3166-1 alpha-2 country code to bias results (e.g. US, GB).",
            advanced=True,
        ),
        DropdownInput(
            name="search_mode",
            display_name="Search Mode",
            info="Search mode: web (default), academic, or sec.",
            options=["web", "academic", "sec"],
            value=None,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Search Results", name="results", method="fetch_content"),
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
    ]

    def _build_payload(self) -> dict:
        max_results_value = self.max_results if self.max_results is not None else 5
        try:
            max_results = int(max_results_value)
        except (TypeError, ValueError):
            max_results = 5
        max_results = max(1, min(max_results, 20))
        payload: dict = {"query": self.query, "max_results": max_results}
        if self.search_recency_filter:
            payload["search_recency_filter"] = self.search_recency_filter
        if self.country:
            payload["country"] = self.country
        if self.search_mode:
            payload["search_mode"] = self.search_mode
        return payload

    def fetch_content(self) -> list[Data]:
        if not self.query:
            error_message = "Query is required."
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Pplx-Integration": _get_integration_header(),
        }
        payload = self._build_payload()

        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                response = client.post(PERPLEXITY_SEARCH_URL, json=payload, headers=headers)
            response.raise_for_status()
            search_results = response.json()
        except httpx.TimeoutException:
            error_message = f"Request timed out ({DEFAULT_TIMEOUT}s). Please try again or adjust parameters."
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.error(f"Perplexity API request failed with HTTP status {status_code}.")
            error_message = f"Perplexity API error: HTTP {status_code}"
            return [Data(error=error_message)]
        except httpx.RequestError as exc:
            error_message = f"Request error occurred: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except ValueError as exc:
            error_message = f"Invalid response format: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]

        data_results: list[Data] = []
        for result in search_results.get("results", []):
            snippet = result.get("snippet", "") or ""
            data_results.append(
                Data(
                    text=snippet,
                    data={
                        "title": result.get("title"),
                        "url": result.get("url"),
                        "snippet": snippet,
                        "date": result.get("date"),
                        "last_updated": result.get("last_updated"),
                    },
                )
            )

        if not data_results:
            data_results.append(Data(text="No results found.", data={"results": []}))

        self.status = data_results
        return data_results

    def fetch_content_dataframe(self) -> DataFrame:
        return DataFrame(self.fetch_content())

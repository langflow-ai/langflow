"""Perplexity Search API component: ranked web results with snippets."""

import httpx
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

SEARCH_URL = "https://api.perplexity.ai/search"
REQUEST_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_RESULTS = 10
MIN_RESULTS = 1
MAX_RESULTS = 20
MAX_DOMAIN_FILTERS = 20
SEARCH_TYPES = ["web", "fast"]
RECENCY_FILTERS = ["hour", "day", "week", "month", "year"]
INTEGRATION_HEADERS = {
    "X-Pplx-Integration": "langflow",
    "User-Agent": "langflow-perplexity-bundle",
}


class PerplexitySearchComponent(Component):
    """Search the web with the Perplexity Search API and return ranked results."""

    display_name = "Perplexity Search"
    description = "Search the web with the Perplexity Search API and return ranked results with snippets."
    documentation = "https://docs.perplexity.ai/docs/search/quickstart"
    icon = "Perplexity"
    name = "PerplexitySearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Perplexity API Key",
            info="Your Perplexity API key. Create one at https://www.perplexity.ai/account/api/keys.",
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The search query to send to the Perplexity Search API.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info=f"Number of results to return, from {MIN_RESULTS} to {MAX_RESULTS}.",
            value=DEFAULT_MAX_RESULTS,
            range_spec=RangeSpec(min=MIN_RESULTS, max=MAX_RESULTS, step=1, step_type="int"),
            advanced=True,
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            info="'web' returns the most relevant results. 'fast' trades some depth for lower latency.",
            options=SEARCH_TYPES,
            value="web",
            advanced=True,
        ),
        MessageTextInput(
            name="search_domain_filter",
            display_name="Domain Filter",
            info=(
                "Comma-separated list of up to 20 domains to restrict results to, for example "
                "'wikipedia.org, arxiv.org'. Prefix a domain with '-' to exclude it."
            ),
            advanced=True,
        ),
        DropdownInput(
            name="search_recency_filter",
            display_name="Recency Filter",
            info="Only return results published within this window. Leave empty for no restriction.",
            options=RECENCY_FILTERS,
            value=None,  # Default to None to make it optional
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="perplexity_search"),
    ]

    def _build_payload(self) -> dict:
        query = (self.query or "").strip()
        if not query:
            msg = "Search Query is required."
            raise ValueError(msg)

        max_results = int(self.max_results or DEFAULT_MAX_RESULTS)
        max_results = max(MIN_RESULTS, min(MAX_RESULTS, max_results))

        payload: dict = {
            "query": query,
            "max_results": max_results,
            "search_type": self.search_type or "web",
        }

        domains = [d.strip() for d in (self.search_domain_filter or "").split(",") if d.strip()]
        if domains:
            if len(domains) > MAX_DOMAIN_FILTERS:
                msg = f"Domain Filter accepts at most {MAX_DOMAIN_FILTERS} domains."
                raise ValueError(msg)
            payload["search_domain_filter"] = domains

        if self.search_recency_filter:
            payload["search_recency_filter"] = self.search_recency_filter

        return payload

    @staticmethod
    def _format_http_error(exc: httpx.HTTPStatusError) -> str:
        status = exc.response.status_code
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text
        if status == httpx.codes.UNAUTHORIZED:
            return "Perplexity Search API rejected the API key (HTTP 401). Check the Perplexity API Key input."
        if status == httpx.codes.UNPROCESSABLE_ENTITY:
            return f"Perplexity Search API rejected the request (HTTP 422): {detail}"
        if status == httpx.codes.TOO_MANY_REQUESTS:
            return "Perplexity Search API rate limit reached (HTTP 429). Retry later."
        return f"Perplexity Search API returned HTTP {status}: {detail}"

    @staticmethod
    def _error_result(error_message: str) -> list[Data]:
        logger.error(error_message)
        return [Data(text=error_message, data={"error": error_message})]

    def _search(self) -> dict:
        """POST the search request and return the decoded JSON body."""
        if not self.api_key:
            msg = "Perplexity API Key is required."
            raise ValueError(msg)

        payload = self._build_payload()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **INTEGRATION_HEADERS,
        }

        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(SEARCH_URL, json=payload, headers=headers)

        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            msg = f"Perplexity Search API returned an unexpected response: {type(body).__name__}"
            raise TypeError(msg)
        return body

    def fetch_content(self) -> list[Data]:
        """Call the Perplexity Search API and return one Data record per result."""
        try:
            body = self._search()
        except httpx.TimeoutException:
            return self._error_result(f"Perplexity Search API request timed out ({REQUEST_TIMEOUT_SECONDS:.0f}s).")
        except httpx.HTTPStatusError as exc:
            return self._error_result(self._format_http_error(exc))
        except httpx.RequestError as exc:
            return self._error_result(f"Perplexity Search API request failed: {exc}")
        except (ValueError, TypeError) as exc:
            return self._error_result(str(exc))

        data_results = [
            Data(
                text=item.get("snippet", ""),
                data={
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", ""),
                    "date": item.get("date"),
                    "last_updated": item.get("last_updated"),
                },
            )
            for item in body.get("results") or []
            if isinstance(item, dict)
        ]

        self.status = data_results
        return data_results

    def perplexity_search(self) -> DataFrame:
        """Return the search results as a DataFrame."""
        return DataFrame(self.fetch_content())

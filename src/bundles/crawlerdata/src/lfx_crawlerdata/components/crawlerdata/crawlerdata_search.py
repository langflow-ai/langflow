import httpx
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

JOBS_ENDPOINT = "https://api.crawlerdata.com/v1/jobs"
DEFAULT_RESULTS = 10
MIN_RESULTS = 1
MAX_RESULTS = 100
FIRST_PAGE = 1
AI_OVERVIEW_TITLE = "Google AI Overview"
DEFAULT_COUNTRY = "us"
DEVICES = ["desktop", "mobile"]
# A live search loads a real Google results page, so it can take well over a minute.
REQUEST_TIMEOUT_SECONDS = 150


def _http_error_message(error: httpx.HTTPStatusError) -> str:
    """Describe a non-2xx CrawlerData response, keeping the API's own error message.

    CrawlerData errors carry ``{"error": {"code": ..., "message": ...}}``.
    """
    response = error.response
    detail = None
    try:
        payload = response.json()
        body_error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(body_error, dict):
            detail = body_error.get("message") or body_error.get("code")
        elif isinstance(body_error, str):
            detail = body_error
    except ValueError:
        detail = None
    reason = detail or response.reason_phrase or "request failed"
    return f"CrawlerData API error {response.status_code}: {reason}"


class CrawlerDataSearchComponent(Component):
    """Component for performing Google web searches using the CrawlerData API."""

    display_name = "CrawlerData Search"
    description = "Search Google with the CrawlerData API: organic results and Google's AI Overview with its sources."
    documentation = "https://crawlerdata.com/apis/google-search-api"
    icon = "search"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Search Query",
            required=True,
            info="The search query to run on Google.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="crawlerdata_api_key",
            display_name="CrawlerData API Key",
            required=True,
            info="Your CrawlerData API key. Create one at https://app.crawlerdata.com (new accounts get free credits).",
            password=True,
        ),
        MessageTextInput(
            name="country",
            display_name="Country",
            value=DEFAULT_COUNTRY,
            required=False,
            advanced=True,
            info="Two-letter country code for the results, for example 'us', 'gb' or 'de'.",
        ),
        MessageTextInput(
            name="language",
            display_name="Language",
            required=False,
            advanced=True,
            info="Two-letter language code, for example 'en' or 'de'.",
        ),
        DropdownInput(
            name="device",
            display_name="Device",
            options=DEVICES,
            value="desktop",
            required=False,
            advanced=True,
            info="Desktop or mobile results.",
        ),
        MessageTextInput(
            name="location",
            display_name="Location",
            required=False,
            advanced=True,
            info="City-level targeting, for example 'Austin,Texas,United States'.",
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=DEFAULT_RESULTS,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=MIN_RESULTS, max=MAX_RESULTS, step=1, step_type="int"),
            info="Maximum number of organic results to return. Google returns about 10 per page.",
        ),
        IntInput(
            name="page",
            display_name="Page",
            value=FIRST_PAGE,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=FIRST_PAGE, max=100, step=1, step_type="int"),
            info="Result page to fetch, starting at 1.",
        ),
        BoolInput(
            name="include_ai_overview",
            display_name="Include AI Overview",
            value=True,
            required=False,
            advanced=True,
            info=(
                "When Google shows an AI Overview for the search, add it as the first row "
                "(title 'Google AI Overview', position 0, with the pages it cites listed under its text)."
            ),
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.  Keep it specific:
        # DuckDuckGo, Tavily, Wikipedia and other search components already expose
        # ``fetch_content_dataframe``, and an Agent cannot hold two tools with the
        # same name.
        Output(display_name="Table", name="dataframe", method="crawlerdata_search"),
    ]

    def _request_body(self) -> dict:
        """Build the JSON body for the CrawlerData jobs endpoint (a live Google Search request)."""
        params: dict = {"query": self.input_value or ""}
        for field in ("country", "language", "device", "location"):
            value = getattr(self, field, None)
            if isinstance(value, str) and value.strip():
                params[field] = value.strip()
        params.setdefault("country", DEFAULT_COUNTRY)
        page = FIRST_PAGE if self.page is None else int(self.page)
        if page > FIRST_PAGE:
            params["page"] = page
        return {"endpoint": "google-search", "params": params, "queue": "live"}

    def _search(self) -> dict:
        """Call the CrawlerData API and return the decoded JSON payload."""
        if not self.crawlerdata_api_key:
            msg = "CrawlerData API key is required. Set the CrawlerData API Key input."
            raise ValueError(msg)

        headers = {
            "Authorization": f"Bearer {self.crawlerdata_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            # Identify the integration to the API; keeps traffic attributable.
            "User-Agent": "langflow-crawlerdata-bundle",
        }
        response = httpx.post(
            JOBS_ENDPOINT,
            json=self._request_body(),
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    def _error_result(self, message: str) -> list[Data]:
        error_data = [Data(text=message, data={"error": message})]
        self.status = error_data
        return error_data

    @staticmethod
    def _result_to_data(result: dict) -> Data:
        snippet = result.get("snippet") or ""
        return Data(
            text=snippet,
            data={
                "title": result.get("title") or "",
                "link": result.get("link") or "",
                "snippet": snippet,
                "position": result.get("position"),
            },
        )

    @staticmethod
    def _ai_overview_to_data(overview: object) -> Data | None:
        """Map Google's AI Overview to one row (``position`` 0), or None when absent.

        The pages it cites are listed under its text, so the row keeps the same four columns as the
        organic rows and an agent reading the table sees the sources.
        """
        if not isinstance(overview, dict):
            return None
        text = overview.get("text")
        if not isinstance(text, str) or not text.strip():
            return None
        cited = [
            f"- {s.get('title') or s['link']}: {s['link']}"
            for s in (overview.get("sources") or [])
            if isinstance(s, dict) and s.get("link")
        ]
        sources_block = "\n\nSources:\n" + "\n".join(cited) if cited else ""
        snippet = text.strip() + sources_block
        return Data(
            text=snippet,
            data={"title": AI_OVERVIEW_TITLE, "link": "", "snippet": snippet, "position": 0},
        )

    def fetch_content(self) -> list[Data]:
        """Execute the search and return the AI Overview (if any) and the organic results as Data objects."""
        try:
            payload = self._search()
        except httpx.HTTPStatusError as e:
            return self._error_result(_http_error_message(e))
        except httpx.HTTPError as e:
            # Some transport errors (timeouts, connect errors) have an empty message, so name the exception type.
            return self._error_result(f"CrawlerData API request failed: {type(e).__name__}: {e}".rstrip(": "))
        except ValueError as e:
            return self._error_result(str(e))

        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            return self._error_result("CrawlerData API returned an unexpected response (expected a result object).")

        requested = DEFAULT_RESULTS if self.max_results is None else int(self.max_results)
        limit = max(MIN_RESULTS, min(requested, MAX_RESULTS))
        organic = [r for r in (result.get("organic_results") or []) if isinstance(r, dict)][:limit]
        data_results = [self._result_to_data(r) for r in organic]

        if self.include_ai_overview:
            overview = self._ai_overview_to_data(result.get("ai_overview"))
            if overview is not None:
                data_results.insert(0, overview)

        self.status = data_results
        return data_results

    def crawlerdata_search(self) -> DataFrame:
        """Run the search and return the results as a DataFrame."""
        return DataFrame(self.fetch_content())

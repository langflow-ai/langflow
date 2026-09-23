import httpx
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

SEARCH_ENDPOINT = "https://api.serpingapi.com/v1/search"
DEFAULT_RESULTS = 10
MIN_RESULTS = 1
MAX_RESULTS = 100
FIRST_PAGE = 1


def _http_error_message(error: httpx.HTTPStatusError) -> str:
    """Describe a non-2xx Serping API response, keeping the API's own error message.

    Serping API errors carry ``{"error": {"code": ..., "message": ...}}``.
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
    return f"Serping API error {response.status_code}: {reason}"


class SerpingApiSearchComponent(Component):
    """Component for performing web searches using the Serping API."""

    display_name = "Serping API Search"
    description = "Search Google organic results with the Serping API."
    documentation = "https://serpingapi.com/docs"
    icon = "search"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Search Query",
            required=True,
            info="The search query to execute with the Serping API.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="serpingapi_api_key",
            display_name="Serping API Key",
            required=True,
            info="Your Serping API key. Get one at https://serpingapi.com.",
            password=True,
        ),
        MessageTextInput(
            name="gl",
            display_name="Country",
            required=False,
            advanced=True,
            info="Country code for the results, for example 'us', 'de' or 'jp'.",
        ),
        MessageTextInput(
            name="hl",
            display_name="Language",
            required=False,
            advanced=True,
            info="Interface language, for example 'en' or 'es'.",
        ),
        MessageTextInput(
            name="location",
            display_name="Location",
            required=False,
            advanced=True,
            info="Locality for the search, for example 'Seattle, Washington, United States'.",
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=DEFAULT_RESULTS,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=MIN_RESULTS, max=MAX_RESULTS, step=1, step_type="int"),
            info="Maximum number of organic results to return (1-100).",
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
    ]

    outputs = [
        # The method name is also the tool name in tool mode.  Keep it specific:
        # DuckDuckGo, Tavily, Wikipedia and other search components already expose
        # ``fetch_content_dataframe``, and an Agent cannot hold two tools with the
        # same name.
        Output(display_name="Table", name="dataframe", method="serpingapi_search"),
    ]

    def _request_body(self) -> dict:
        """Build the JSON body for the Serping API search endpoint."""
        requested = DEFAULT_RESULTS if self.max_results is None else int(self.max_results)
        num = max(MIN_RESULTS, min(requested, MAX_RESULTS))
        body: dict = {"q": self.input_value or "", "num": num}
        for field in ("gl", "hl", "location"):
            value = getattr(self, field, None)
            if isinstance(value, str) and value.strip():
                body[field] = value.strip()
        page = FIRST_PAGE if self.page is None else int(self.page)
        if page > FIRST_PAGE:
            body["page"] = page
        return body

    def _search(self) -> dict:
        """Call the Serping API search endpoint and return the decoded JSON payload."""
        if not self.serpingapi_api_key:
            msg = "Serping API key is required. Set the Serping API Key input."
            raise ValueError(msg)

        headers = {
            "X-API-Key": self.serpingapi_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            # Identify the integration to the API; keeps traffic attributable.
            "User-Agent": "langflow-serpingapi-bundle",
        }
        response = httpx.post(SEARCH_ENDPOINT, json=self._request_body(), headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def _error_result(self, message: str) -> list[Data]:
        error_data = [Data(text=message, data={"error": message})]
        self.status = error_data
        return error_data

    @staticmethod
    def _result_to_data(result: dict) -> Data:
        snippet = result.get("snippet", "")
        return Data(
            text=snippet,
            data={
                "title": result.get("title", ""),
                "link": result.get("link", ""),
                "snippet": snippet,
                "position": result.get("position"),
            },
        )

    def fetch_content(self) -> list[Data]:
        """Execute the search and return the organic results as Data objects."""
        try:
            payload = self._search()
        except httpx.HTTPStatusError as e:
            return self._error_result(_http_error_message(e))
        except (httpx.HTTPError, ValueError) as e:
            return self._error_result(str(e))

        if not isinstance(payload, dict):
            return self._error_result("Serping API returned an unexpected response (expected a JSON object).")

        results = payload.get("organic") or []
        data_results = [self._result_to_data(result) for result in results if isinstance(result, dict)]
        self.status = data_results
        return data_results

    def serpingapi_search(self) -> DataFrame:
        """Run the search and return the organic results as a DataFrame."""
        return DataFrame(self.fetch_content())

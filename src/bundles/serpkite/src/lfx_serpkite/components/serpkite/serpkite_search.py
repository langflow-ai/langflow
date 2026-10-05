import httpx
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

SEARCH_ENDPOINT = "https://api.serpkite.com/v1/search"
DEFAULT_RESULTS = 10
MIN_RESULTS = 10
MAX_RESULTS = 100
FIRST_PAGE = 1
MAX_PAGE = 10
MAX_ERROR_DETAIL = 500


def _http_error_message(error: httpx.HTTPStatusError) -> str:
    """Describe a non-2xx SerpKite response, keeping the API's own error message.

    SerpKite errors carry ``{"error": {"code": ..., "message": ...}}``. A
    non-JSON body (for example from a proxy) is kept, trimmed to 500 characters.
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
        detail = response.text.strip()[:MAX_ERROR_DETAIL] or None
    reason = detail or response.reason_phrase or "request failed"
    return f"SerpKite error {response.status_code}: {reason}"


class SerpKiteSearchComponent(Component):
    """Component for performing web searches using SerpKite."""

    display_name = "SerpKite Search"
    description = "Search Google organic results with SerpKite."
    documentation = "https://serpkite.com/docs"
    icon = "search"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Search Query",
            required=True,
            info="The search query to execute with SerpKite.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="serpkite_api_key",
            display_name="SerpKite Key",
            required=True,
            info="Your SerpKite key. Get one at https://app.serpkite.com/keys.",
            password=True,
        ),
        MessageTextInput(
            name="country",
            display_name="Country",
            required=False,
            advanced=True,
            info="Country code for the results, for example 'us', 'de' or 'jp'.",
        ),
        MessageTextInput(
            name="language",
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
            info="Maximum number of organic results to return (10-100).",
        ),
        IntInput(
            name="page",
            display_name="Page",
            value=FIRST_PAGE,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=FIRST_PAGE, max=MAX_PAGE, step=1, step_type="int"),
            info="Result page to fetch, starting at 1.",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.  Keep it specific:
        # DuckDuckGo, Tavily, Wikipedia and other search components already expose
        # ``fetch_content_dataframe``, and an Agent cannot hold two tools with the
        # same name.
        Output(display_name="Table", name="dataframe", method="serpkite_search"),
    ]

    def _request_body(self) -> dict:
        """Build the JSON body for the SerpKite search endpoint."""
        requested = DEFAULT_RESULTS if self.max_results is None else int(self.max_results)
        num = max(MIN_RESULTS, min(requested, MAX_RESULTS))
        body: dict = {"q": self.input_value or "", "num": num}
        for field in ("country", "language", "location"):
            value = getattr(self, field, None)
            if isinstance(value, str) and value.strip():
                body[field] = value.strip()
        page = FIRST_PAGE if self.page is None else int(self.page)
        if not FIRST_PAGE <= page <= MAX_PAGE:
            msg = "Page must be between 1 and 10."
            raise ValueError(msg)
        if num > DEFAULT_RESULTS and page > FIRST_PAGE:
            msg = "Search depth above 10 results requires page 1."
            raise ValueError(msg)
        if page > FIRST_PAGE:
            body["page"] = page
        return body

    async def _search(self) -> dict:
        """Call the SerpKite search endpoint and return the decoded JSON payload."""
        if not self.serpkite_api_key:
            msg = "SerpKite key is required. Set the SerpKite Key input."
            raise ValueError(msg)

        headers = {
            "Authorization": f"Bearer {self.serpkite_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            # Identify the integration to the API; keeps traffic attributable.
            "User-Agent": "langflow-serpkite-bundle",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(SEARCH_ENDPOINT, json=self._request_body(), headers=headers)
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

    async def fetch_content(self) -> list[Data]:
        """Execute the search and return the organic results as Data objects."""
        try:
            payload = await self._search()
        except httpx.HTTPStatusError as e:
            return self._error_result(_http_error_message(e))
        except (httpx.HTTPError, ValueError) as e:
            return self._error_result(str(e))

        if not isinstance(payload, dict):
            return self._error_result("SerpKite returned an unexpected response (expected a JSON object).")

        results = payload.get("results", [])
        if not isinstance(results, list):
            return self._error_result("SerpKite returned an unexpected results field (expected a list).")
        data_results = [self._result_to_data(result) for result in results if isinstance(result, dict)]
        self.status = data_results
        return data_results

    async def serpkite_search(self) -> DataFrame:
        """Run the search and return the organic results as a DataFrame."""
        return DataFrame(await self.fetch_content())

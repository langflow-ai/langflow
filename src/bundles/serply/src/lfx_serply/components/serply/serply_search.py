from urllib.parse import urlencode

import httpx
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

SEARCH_ENDPOINT = "https://api.serply.io/v1/search/"
DEFAULT_RESULTS = 10
MIN_RESULTS = 1
MAX_RESULTS = 100


def _http_error_message(error: httpx.HTTPStatusError) -> str:
    """Describe a non-2xx Serply response, keeping the API's own ``detail`` reason."""
    response = error.response
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    reason = detail or response.reason_phrase or "request failed"
    return f"Serply API error {response.status_code}: {reason}"


class SerplySearchComponent(Component):
    """Component for performing web searches using the Serply SERP API."""

    display_name = "Serply Search"
    description = "Search Google organic results with the Serply API."
    documentation = "https://serply.io/docs"
    icon = "search"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Search Query",
            required=True,
            info="The search query to execute with Serply.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="serply_api_key",
            display_name="Serply API Key",
            required=True,
            info="Your Serply API key. Get one at https://serply.io.",
            password=True,
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
    ]

    outputs = [
        # The method name is also the tool name in tool mode.  Keep it specific:
        # DuckDuckGo, Tavily, Wikipedia and other search components already expose
        # ``fetch_content_dataframe``, and an Agent cannot hold two tools with the
        # same name.
        Output(display_name="Table", name="dataframe", method="serply_search"),
    ]

    def _search(self) -> dict:
        """Call the Serply search endpoint and return the decoded JSON payload."""
        if not self.serply_api_key:
            msg = "Serply API key is required. Set the Serply API Key input."
            raise ValueError(msg)

        requested = DEFAULT_RESULTS if self.max_results is None else int(self.max_results)
        num = max(MIN_RESULTS, min(requested, MAX_RESULTS))
        query = urlencode({"q": self.input_value or "", "num": num})
        headers = {
            "X-Api-Key": self.serply_api_key,
            "Accept": "application/json",
            # Serply sits behind Cloudflare, which blocks the default httpx
            # User-Agent with a 1010 error, so send an explicit one.
            "User-Agent": "langflow-serply-bundle",
        }
        response = httpx.get(f"{SEARCH_ENDPOINT}?{query}", headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def _error_result(self, message: str) -> list[Data]:
        error_data = [Data(text=message, data={"error": message})]
        self.status = error_data
        return error_data

    @staticmethod
    def _result_to_data(result: dict) -> Data:
        description = result.get("description", "")
        return Data(
            text=description,
            data={
                "title": result.get("title", ""),
                "link": result.get("link", ""),
                "description": description,
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
            return self._error_result("Serply API returned an unexpected response (expected a JSON object).")

        results = payload.get("results") or []
        data_results = [self._result_to_data(result) for result in results if isinstance(result, dict)]
        self.status = data_results
        return data_results

    def serply_search(self) -> DataFrame:
        """Run the search and return the organic results as a DataFrame."""
        return DataFrame(self.fetch_content())

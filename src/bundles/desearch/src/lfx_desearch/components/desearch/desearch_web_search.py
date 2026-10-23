import httpx
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_desearch.components.desearch._client import desearch_request, http_error_message


class DesearchWebSearchComponent(Component):
    """Web search through the Desearch API."""

    display_name = "Desearch Web Search"
    description = "Search the web with Desearch and return titles, links and snippets."
    documentation = "https://www.desearch.ai/docs"
    icon = "search"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Search Query",
            required=True,
            info="The search query to run with Desearch.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="desearch_api_key",
            display_name="Desearch API Key",
            required=True,
            info="Your Desearch API key. Create one at https://console.desearch.ai/api-keys.",
            password=True,
        ),
        IntInput(
            name="offset",
            display_name="Offset",
            value=0,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=0, max=1000, step=10, step_type="int"),
            info="Number of results to skip, for paging (0, 10, 20 and so on).",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode, so keep it specific.
        Output(display_name="Table", name="dataframe", method="desearch_web_search"),
    ]

    def _params(self) -> dict:
        params: dict = {"query": self.input_value or ""}
        offset = int(self.offset or 0)
        if offset > 0:
            params["start"] = offset
        return params

    def _error_result(self, message: str) -> list[Data]:
        error_data = [Data(text=message, data={"error": message})]
        self.status = error_data
        return error_data

    def fetch_content(self) -> list[Data]:
        """Run the search and return the results as Data objects."""
        try:
            payload = desearch_request("GET", "/web", self.desearch_api_key, params=self._params(), timeout=30)
        except httpx.HTTPStatusError as e:
            return self._error_result(http_error_message(e))
        except (httpx.HTTPError, ValueError) as e:
            return self._error_result(str(e))
        if not isinstance(payload, dict):
            return self._error_result("Desearch returned an unexpected response (expected a JSON object).")
        results = []
        for item in payload.get("data") or []:
            if not isinstance(item, dict):
                continue
            snippet = item.get("snippet", "")
            results.append(
                Data(
                    text=snippet,
                    data={"title": item.get("title", ""), "link": item.get("link", ""), "snippet": snippet},
                )
            )
        self.status = results
        return results

    def desearch_web_search(self) -> DataFrame:
        """Run the search and return the results as a DataFrame."""
        return DataFrame(self.fetch_content())

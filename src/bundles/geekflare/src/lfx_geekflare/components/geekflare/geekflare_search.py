from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._api import GeekflareAPIError, call_api

DEFAULT_RESULTS = 10
MIN_RESULTS = 1
MAX_RESULTS = 100


class GeekflareSearchComponent(Component):
    """Search the web, news, or images with Geekflare, or fetch the full Google SERP."""

    display_name = "Geekflare Search"
    description = "Search the live web, news, or images with Geekflare, or get the full Google results page."
    documentation = "https://docs.geekflare.com/guides/search"
    icon = "Geekflare"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Search Query",
            required=True,
            info="The search query to execute with Geekflare.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="geekflare_api_key",
            display_name="Geekflare API Key",
            required=True,
            info="Your Geekflare API key. Get one at https://dash.geekflare.com.",
            password=True,
        ),
        DropdownInput(
            name="source",
            display_name="Source",
            options=["web", "news", "images"],
            value="web",
            advanced=True,
            info="Search source.",
        ),
        BoolInput(
            name="serp",
            display_name="Google SERP",
            value=False,
            advanced=True,
            info="Return the organic results from the full Google results page.",
        ),
        MessageTextInput(
            name="location",
            display_name="Country",
            required=False,
            advanced=True,
            info="Country code (ISO alpha-2) for localized results, for example 'us' or 'de'.",
        ),
        MessageTextInput(
            name="city",
            display_name="City",
            required=False,
            advanced=True,
            info="City for localized results, e.g. 'London,England,United Kingdom'. Takes priority over Country.",
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=DEFAULT_RESULTS,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=MIN_RESULTS, max=MAX_RESULTS, step=1, step_type="int"),
            info="Maximum number of results to return (1-100).",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode; keep it unique across
        # search components so an Agent can hold several of them.
        Output(display_name="Table", name="dataframe", method="geekflare_search"),
    ]

    def _request_body(self) -> dict:
        requested = DEFAULT_RESULTS if self.max_results is None else int(self.max_results)
        body: dict = {
            "query": self.input_value or "",
            "limit": max(MIN_RESULTS, min(requested, MAX_RESULTS)),
            "source": self.source or "web",
            "serp": bool(self.serp),
        }
        for field in ("location", "city"):
            value = getattr(self, field, None)
            if isinstance(value, str) and value.strip():
                body[field] = value.strip()
        return body

    @staticmethod
    def _to_rows(payload: dict) -> list[Data]:
        data = payload.get("data")
        # SERP mode returns {"organic": [...], ...}; standard search returns a list.
        items = (data.get("organic") or []) if isinstance(data, dict) else (data or [])
        rows = []
        for item in items:
            if not isinstance(item, dict):
                continue
            snippet = item.get("snippet") or item.get("description") or ""
            rows.append(
                Data(
                    text=snippet,
                    data={
                        "title": item.get("title", ""),
                        "link": item.get("url") or item.get("link", ""),
                        "snippet": snippet,
                        "position": item.get("position"),
                    },
                )
            )
        return rows

    def fetch_content(self) -> list[Data]:
        """Execute the search and return the results as Data objects."""
        try:
            payload = call_api(self.geekflare_api_key, "search", self._request_body())
        except GeekflareAPIError as e:
            error = [Data(text=str(e), data={"error": str(e)})]
            self.status = error
            return error
        rows = self._to_rows(payload)
        self.status = rows
        return rows

    def geekflare_search(self) -> DataFrame:
        """Run the search and return the results as a DataFrame."""
        return DataFrame(self.fetch_content())

import httpx
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_contextfetch.components.contextfetch._common import API_BASE, error_result, http_error_message, post

SEARCH_ENDPOINT = f"{API_BASE}/v1/search"
DEFAULT_RESULTS = 5
MIN_RESULTS = 1
MAX_RESULTS = 25
# Page content option label -> request flag under ``contents`` and the result field it fills.
CONTENT_FIELDS = {
    "Pruned Context": "prunedContext",
    "Highlights": "highlights",
    "Full Text": "text",
}
DEFAULT_CONTENT = "Pruned Context"


def split_list(value: str | None) -> list[str]:
    """Split a comma- or newline-separated input into trimmed, non-empty items."""
    if not isinstance(value, str):
        return []
    return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]


def content_text(result: dict, field: str) -> str:
    """Return the page content for ``field`` as text; highlights are joined with blank lines."""
    value = result.get(field)
    if isinstance(value, list):
        return "\n\n".join(str(v) for v in value)
    return value if isinstance(value, str) else ""


class ContextFetchSearchComponent(Component):
    """Component for searching the web with the ContextFetch API."""

    display_name = "ContextFetch Search"
    description = "Search the web with ContextFetch and get results with page content as Markdown."
    documentation = "https://contextfetch.dev/docs"
    icon = "ContextFetch"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Search Query",
            required=True,
            info="What to search the web for (up to 2,000 characters).",
            tool_mode=True,
        ),
        SecretStrInput(
            name="contextfetch_api_key",
            display_name="ContextFetch API Key",
            required=True,
            info="Your ContextFetch API key. Get a free key at https://contextfetch.dev/docs.",
            password=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=DEFAULT_RESULTS,
            required=False,
            range_spec=RangeSpec(min=MIN_RESULTS, max=MAX_RESULTS, step=1, step_type="int"),
            info="Maximum number of results to return (1-25).",
        ),
        DropdownInput(
            name="content",
            display_name="Page Content",
            options=list(CONTENT_FIELDS),
            value=DEFAULT_CONTENT,
            advanced=True,
            info=(
                "What page content to add to each result: Pruned Context (the relevant chunks joined in page "
                "order, to save tokens), Highlights (the chunks most relevant to the query) or Full Text "
                "(the whole page as Markdown)."
            ),
        ),
        MessageTextInput(
            name="include_domains",
            display_name="Include Domains",
            required=False,
            advanced=True,
            info="Comma-separated domains. Only results from these domains are returned.",
        ),
        MessageTextInput(
            name="exclude_domains",
            display_name="Exclude Domains",
            required=False,
            advanced=True,
            info="Comma-separated domains to leave out of the results.",
        ),
        MessageTextInput(
            name="start_published_date",
            display_name="Published After",
            required=False,
            advanced=True,
            info="Only return results published on or after this date (YYYY-MM-DD).",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.  Keep it specific:
        # other search components already expose ``fetch_content_dataframe``, and
        # an Agent cannot hold two tools with the same name.
        Output(display_name="Table", name="dataframe", method="contextfetch_search"),
    ]

    def _content_field(self) -> str:
        return CONTENT_FIELDS.get(self.content or DEFAULT_CONTENT, CONTENT_FIELDS[DEFAULT_CONTENT])

    def _request_body(self) -> dict:
        """Build the JSON body for the ContextFetch search endpoint."""
        requested = DEFAULT_RESULTS if self.max_results is None else int(self.max_results)
        field = self._content_field()
        body: dict = {
            "query": self.input_value or "",
            "numResults": max(MIN_RESULTS, min(requested, MAX_RESULTS)),
            "contents": {name: name == field for name in CONTENT_FIELDS.values()},
        }
        for name, key in (("include_domains", "includeDomains"), ("exclude_domains", "excludeDomains")):
            domains = split_list(getattr(self, name, None))
            if domains:
                body[key] = domains
        date = getattr(self, "start_published_date", None)
        if isinstance(date, str) and date.strip():
            body["startPublishedDate"] = date.strip()
        return body

    def fetch_content(self) -> list[Data]:
        """Execute the search and return the results as Data objects."""
        try:
            payload = post(self.contextfetch_api_key, SEARCH_ENDPOINT, self._request_body())
        except httpx.HTTPStatusError as e:
            return error_result(self, http_error_message(e))
        except (httpx.HTTPError, ValueError) as e:
            return error_result(self, str(e))

        if not isinstance(payload, dict):
            return error_result(self, "ContextFetch returned an unexpected response (expected a JSON object).")

        field = self._content_field()
        data_results = [
            Data(
                text=content_text(result, field),
                data={
                    "title": result.get("title") or "",
                    "url": result.get("url") or "",
                    "published_date": result.get("publishedDate"),
                    "content": content_text(result, field),
                },
            )
            for result in payload.get("results") or []
            if isinstance(result, dict)
        ]
        self.status = data_results
        return data_results

    def contextfetch_search(self) -> DataFrame:
        """Run the search and return the results as a DataFrame."""
        return DataFrame(self.fetch_content())

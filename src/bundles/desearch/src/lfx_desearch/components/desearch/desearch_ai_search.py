import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, MessageTextInput, MultiselectInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output
from lfx_desearch.components.desearch._client import desearch_request, http_error_message

SOURCES = ["web", "twitter", "reddit", "hackernews", "arxiv", "wikipedia"]
DEFAULT_SOURCES = ["web", "twitter"]
DATE_FILTERS = [
    "ANY_TIME",
    "PAST_24_HOURS",
    "PAST_2_DAYS",
    "PAST_WEEK",
    "PAST_2_WEEKS",
    "PAST_MONTH",
    "PAST_2_MONTHS",
    "PAST_YEAR",
    "PAST_2_YEARS",
]


TITLE_MAX_CHARS = 100


def _short_title(item: dict) -> str:
    """Use the result title, or the first line of a post's text, kept to one short line."""
    title = str(item.get("title") or item.get("text") or "").strip()
    first_line = title.splitlines()[0] if title else ""
    if len(first_line) > TITLE_MAX_CHARS:
        first_line = first_line[: TITLE_MAX_CHARS - 3].rstrip() + "..."
    return first_line


def collect_links(payload: dict) -> list[dict]:
    """Collect unique title/link pairs from every list of results in the payload."""
    links: list[dict] = []
    seen: set[str] = set()
    for value in payload.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            url = item.get("link") or item.get("url")
            if url and url not in seen:
                seen.add(url)
                links.append({"title": _short_title(item), "link": url})
    return links


class DesearchAISearchComponent(Component):
    """AI search with a sourced answer through the Desearch API."""

    display_name = "Desearch AI Search"
    description = "Get an AI answer with links to its sources from web, X, Reddit, Hacker News, arXiv and Wikipedia."
    documentation = "https://www.desearch.ai/docs"
    icon = "search"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Prompt",
            required=True,
            info="The question or topic to research.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="desearch_api_key",
            display_name="Desearch API Key",
            required=True,
            info="Your Desearch API key. Create one at https://console.desearch.ai/api-keys.",
            password=True,
        ),
        MultiselectInput(
            name="sources",
            display_name="Sources",
            options=SOURCES,
            value=DEFAULT_SOURCES,
            required=False,
            advanced=True,
            info="Sources to search. Defaults to web and twitter.",
        ),
        DropdownInput(
            name="date_filter",
            display_name="Date Range",
            options=DATE_FILTERS,
            value="ANY_TIME",
            required=False,
            advanced=True,
            info="Only use sources from this period.",
        ),
    ]

    outputs = [
        Output(display_name="Answer", name="answer", method="desearch_ai_search"),
        # The answer already lists its sources, so only the answer is exposed as a tool.
        Output(display_name="Sources", name="sources_table", method="desearch_ai_sources", tool_mode=False),
    ]

    def _body(self) -> dict:
        selected = [s for s in (self.sources or []) if s in SOURCES] or list(DEFAULT_SOURCES)
        body: dict = {"prompt": self.input_value or "", "tools": selected, "streaming": False}
        if self.date_filter and self.date_filter != "ANY_TIME":
            body["date_filter"] = self.date_filter
        return body

    def _run(self) -> tuple[dict | None, str | None]:
        """Call the API once per request body, so both outputs share one successful search."""
        body = self._body()
        cache_key = repr(sorted(body.items()))
        cached = getattr(self, "_desearch_cache", None)
        if cached and cached[0] == cache_key:
            return cached[1], cached[2]
        payload: dict | None = None
        error: str | None = None
        try:
            result = desearch_request("POST", "/desearch/ai/search", self.desearch_api_key, json=body, timeout=120)
            if isinstance(result, dict):
                payload = result
            else:
                error = "Desearch returned an unexpected response (expected a JSON object)."
        except httpx.HTTPStatusError as e:
            error = http_error_message(e)
        except (httpx.HTTPError, ValueError) as e:
            error = str(e)
        if payload is not None:
            self._desearch_cache = (cache_key, payload, None)
        return payload, error

    def desearch_ai_search(self) -> Message:
        """Return the AI answer followed by its source links."""
        payload, error = self._run()
        if error:
            self.status = error
            return Message(text=error)
        answer = str(payload.get("completion") or "").strip()
        links = collect_links(payload)
        parts = [answer] if answer else []
        if links:
            parts.append("Sources:\n" + "\n".join(f"- {item['title']} {item['link']}".strip() for item in links))
        text = "\n\n".join(parts) or "No results."
        self.status = text
        return Message(text=text)

    def desearch_ai_sources(self) -> DataFrame:
        """Return the source links as a DataFrame."""
        payload, error = self._run()
        if error:
            return DataFrame([Data(text=error, data={"error": error})])
        return DataFrame([Data(text=item["title"], data=item) for item in collect_links(payload)])

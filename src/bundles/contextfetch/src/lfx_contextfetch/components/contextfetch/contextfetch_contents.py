import re

import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_contextfetch.components.contextfetch._common import API_BASE, error_result, http_error_message, post

CONTENTS_ENDPOINT = f"{API_BASE}/v1/contents"
MAX_URLS = 100


def split_urls(value: str | None) -> list[str]:
    """Split on whitespace, or on a comma that starts the next URL, so a comma inside one URL is kept."""
    if not isinstance(value, str):
        return []
    return [url for url in re.split(r"\s+|,(?=\s*https?://)", value.strip()) if url]


class ContextFetchContentsComponent(Component):
    """Component for fetching web pages as Markdown with the ContextFetch API."""

    display_name = "ContextFetch Get Contents"
    description = "Fetch one or more web pages as Markdown with ContextFetch."
    documentation = "https://contextfetch.dev/docs"
    icon = "ContextFetch"

    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            required=True,
            info="One or more public http(s) page URLs (up to 100), separated by commas, spaces or new lines.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="contextfetch_api_key",
            display_name="ContextFetch API Key",
            required=True,
            info="Your ContextFetch API key. Get a free key at https://contextfetch.dev/docs.",
            password=True,
        ),
        MessageTextInput(
            name="highlights_query",
            display_name="Highlights Query",
            required=False,
            advanced=True,
            info="If set, each page also gets the chunks most relevant to this query as highlights.",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode; keep it ContextFetch-specific.
        Output(display_name="Table", name="dataframe", method="contextfetch_get_contents"),
    ]

    def _request_body(self) -> dict:
        """Build the JSON body for the ContextFetch contents endpoint."""
        body: dict = {"urls": split_urls(self.urls)[:MAX_URLS], "text": True}
        query = getattr(self, "highlights_query", None)
        if isinstance(query, str) and query.strip():
            body["highlights"] = {"query": query.strip()}
        return body

    def fetch_content(self) -> list[Data]:
        """Fetch the pages and return one Data per URL; URLs that did not load carry ``error``."""
        body = self._request_body()
        if not body["urls"]:
            return error_result(self, "At least one URL is required.")
        try:
            payload = post(self.contextfetch_api_key, CONTENTS_ENDPOINT, body)
        except httpx.HTTPStatusError as e:
            return error_result(self, http_error_message(e))
        except (httpx.HTTPError, ValueError) as e:
            return error_result(self, str(e))

        if not isinstance(payload, dict):
            return error_result(self, "ContextFetch returned an unexpected response (expected a JSON object).")

        data_results = [
            Data(
                text=result.get("text") or "",
                data={
                    "title": result.get("title") or "",
                    "url": result.get("url") or "",
                    "published_date": result.get("publishedDate"),
                    "text": result.get("text") or "",
                    "highlights": result.get("highlights") or [],
                },
            )
            for result in payload.get("results") or []
            if isinstance(result, dict)
        ]
        for status in payload.get("statuses") or []:
            if isinstance(status, dict) and status.get("status") == "error":
                error = status.get("error") if isinstance(status.get("error"), dict) else {}
                message = error.get("message") or "Page did not load"
                data_results.append(Data(text=message, data={"url": status.get("id") or "", "error": message}))
        self.status = data_results
        return data_results

    def contextfetch_get_contents(self) -> DataFrame:
        """Fetch the pages and return them as a DataFrame."""
        return DataFrame(self.fetch_content())

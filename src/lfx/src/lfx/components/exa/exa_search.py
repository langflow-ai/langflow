from exa_py import Exa
from langchain_core.tools import tool

from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool
from lfx.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    Output,
    SecretStrInput,
)

EXA_INTEGRATION_NAME = "langflow-integration"


class ExaSearchToolkit(Component):
    display_name = "Exa Search"
    description = "Exa search and contents tools for agents and MCP clients."
    documentation = "https://docs.exa.ai/reference/getting-started"
    beta = True
    name = "ExaSearch"
    icon = "ExaSearch"

    inputs = [
        SecretStrInput(
            name="exa_api_key",
            display_name="Exa API Key",
            info="Get one at https://dashboard.exa.ai/api-keys",
            password=True,
        ),
        # Kept for backward compatibility with flows saved before the field
        # was renamed. Hidden from the UI; users should fill in `exa_api_key`.
        SecretStrInput(
            name="metaphor_api_key",
            display_name="Metaphor API Key (legacy)",
            info="Deprecated. Use Exa API Key instead.",
            password=True,
            advanced=True,
            show=False,
        ),
        DropdownInput(
            name="search_type",
            display_name="Search type",
            options=["auto", "fast", "instant", "deep"],
            value="auto",
            info="Latency vs. depth tradeoff. `auto` is recommended for most use cases.",
        ),
        IntInput(
            name="search_num_results",
            display_name="Number of results",
            value=10,
        ),
        BoolInput(
            name="include_highlights",
            display_name="Include highlights",
            value=True,
            advanced=True,
            info="Token-efficient extracts of the most relevant text per result. Recommended default.",
        ),
        IntInput(
            name="highlights_max_characters",
            display_name="Highlights max characters",
            value=0,
            advanced=True,
            info="Optional cap on the length of each highlight, in characters. 0 leaves it at Exa's default.",
        ),
        BoolInput(
            name="include_text",
            display_name="Include full text",
            value=False,
            advanced=True,
            info="Return full page text. Off by default; prefer highlights for token efficiency.",
        ),
        DropdownInput(
            name="category",
            display_name="Category",
            options=[
                "",
                "company",
                "people",
                "research paper",
                "news",
                "personal site",
                "financial report",
            ],
            value="",
            advanced=True,
            info="Restrict to a specific Exa data category. Leave empty for general web search.",
        ),
        IntInput(
            name="max_age_hours",
            display_name="Max age (hours)",
            value=0,
            advanced=True,
            info=(
                "Max age of cached content (in hours) before refetching. "
                "0 = always refetch. -1 = never refetch (use cache only)."
            ),
        ),
        MessageTextInput(
            name="include_domains",
            display_name="Include domains",
            value="",
            advanced=True,
            info="Comma-separated allowlist of domains.",
        ),
        MessageTextInput(
            name="exclude_domains",
            display_name="Exclude domains",
            value="",
            advanced=True,
            info="Comma-separated denylist of domains.",
        ),
        MessageTextInput(
            name="start_published_date",
            display_name="Start published date",
            value="",
            advanced=True,
            info="ISO date (YYYY-MM-DD). Only return results published on or after this date.",
        ),
        MessageTextInput(
            name="end_published_date",
            display_name="End published date",
            value="",
            advanced=True,
            info="ISO date (YYYY-MM-DD). Only return results published on or before this date.",
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_toolkit"),
    ]

    def _resolved_api_key(self) -> str:
        return self.exa_api_key or self.metaphor_api_key

    def _build_client(self) -> Exa:
        client = Exa(api_key=self._resolved_api_key())
        client.headers["x-exa-integration"] = EXA_INTEGRATION_NAME
        return client

    def _highlights_value(self):
        if not self.include_highlights:
            return None
        if self.highlights_max_characters and self.highlights_max_characters > 0:
            return {"max_characters": self.highlights_max_characters}
        return True

    def _contents(self) -> dict | None:
        contents: dict = {}
        highlights = self._highlights_value()
        if highlights is not None:
            contents["highlights"] = highlights
        if self.include_text:
            contents["text"] = True
        if self.max_age_hours and self.max_age_hours != 0:
            contents["max_age_hours"] = self.max_age_hours
        return contents or None

    @staticmethod
    def _split_csv(raw: str) -> list[str] | None:
        items = [s.strip() for s in (raw or "").split(",") if s.strip()]
        return items or None

    def build_toolkit(self) -> Tool:
        client = self._build_client()
        contents = self._contents()
        category = self.category or None
        include_domains = self._split_csv(self.include_domains)
        exclude_domains = self._split_csv(self.exclude_domains)
        start_published_date = (self.start_published_date or "").strip() or None
        end_published_date = (self.end_published_date or "").strip() or None

        @tool
        def search(query: str):
            """Search the web with Exa and return results with optional highlights."""
            kwargs: dict = {
                "type": self.search_type,
                "num_results": self.search_num_results,
            }
            if contents is not None:
                kwargs["contents"] = contents
            if category:
                kwargs["category"] = category
            if include_domains:
                kwargs["include_domains"] = include_domains
            if exclude_domains:
                kwargs["exclude_domains"] = exclude_domains
            if start_published_date:
                kwargs["start_published_date"] = start_published_date
            if end_published_date:
                kwargs["end_published_date"] = end_published_date
            return client.search(query, **kwargs)

        @tool
        def get_contents(ids: list[str]):
            """Fetch contents (highlights and/or text) for result IDs returned by `search`."""
            kwargs: dict = {}
            highlights = self._highlights_value()
            if highlights is not None:
                kwargs["highlights"] = highlights
            if self.include_text:
                kwargs["text"] = True
            if self.max_age_hours and self.max_age_hours != 0:
                kwargs["max_age_hours"] = self.max_age_hours
            return client.get_contents(ids, **kwargs)

        return [search, get_contents]

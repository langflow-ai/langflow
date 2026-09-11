from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._client import comma_separated_values, context_api_key_input, defined_values, request_context


class ContextSearchWebComponent(Component):
    display_name = "Context.dev Web Search"
    description = "Search the live web with optional domain, freshness, and Markdown controls."
    documentation = "https://docs.context.dev/api-reference/web-scraping/search"
    icon = "Context"

    inputs = [
        context_api_key_input(),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="Natural-language query or Google-style search expression.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="num_results",
            display_name="Number of Results",
            value=10,
            range_spec=RangeSpec(min=10, max=100, step=1, step_type="int"),
        ),
        MessageTextInput(
            name="include_domains",
            display_name="Include Domains",
            info="Optional comma-separated domain allowlist.",
            advanced=True,
        ),
        MessageTextInput(
            name="exclude_domains",
            display_name="Exclude Domains",
            info="Optional comma-separated domain blocklist.",
            advanced=True,
        ),
        DropdownInput(
            name="freshness",
            display_name="Freshness",
            options=["", "last_24_hours", "last_week", "last_month", "last_year"],
            value="",
            advanced=True,
        ),
        BoolInput(
            name="include_markdown",
            display_name="Include Page Markdown",
            info="Scrape Markdown for each search result.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="use_main_content_only",
            display_name="Main Content Only",
            info="Remove navigation, headers, footers, and sidebars from included Markdown.",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Search Results", name="results", method="search")]

    async def search(self) -> Data:
        payload = defined_values(
            {
                "query": str(self.query).strip(),
                "numResults": self.num_results,
                "includeDomains": comma_separated_values(self.include_domains),
                "excludeDomains": comma_separated_values(self.exclude_domains),
                "freshness": self.freshness or None,
                "markdownOptions": {
                    "enabled": bool(self.include_markdown),
                    "useMainContentOnly": bool(self.use_main_content_only),
                },
            }
        )
        response = await request_context("POST", "/web/search", self.api_key, json=payload)
        self.status = response
        return Data(data=response)

from contextlib import suppress

from langchain_core.tools import tool
from linkup import LinkupClient

from langflow.custom.custom_component.component import Component
from langflow.field_typing import Tool
from langflow.io import BoolInput, MessageTextInput, Output, SecretStrInput, StrInput


class LinkupSearchToolkit(Component):
    """A component that provides a toolkit for searching and retrieving content using the Linkup Search API."""

    display_name: str = "Linkup Search"
    description: str = "Linkup Search toolkit for search and content retrieval"
    icon: str = "LinkupSearch"
    priority: int = 1
    name: str = "LinkupSearch"

    inputs = [
        SecretStrInput(
            name="linkup_api_key",
            display_name="Linkup API Key",
            password=True,
        ),
        BoolInput(
            name="include_images",
            display_name="Include Images",
            value=False,
        ),
        StrInput(
            name="search_depth",
            display_name="Search Depth",
            value="standard",
        ),
        StrInput(
            name="from_date",
            display_name="From Date",
            info="Date in ISO format (YYYY-MM-DD)",
        ),
        StrInput(
            name="to_date",
            display_name="To Date",
            info="Date in ISO format (YYYY-MM-DD)",
        ),
        MessageTextInput(
            name="include_domains",
            display_name="Include Domains",
            info="Comma-separated list of domains to include in the search results.",
        ),
        MessageTextInput(
            name="exclude_domains",
            display_name="Exclude Domains",
            info="Comma-separated list of domains to exclude from the search results.",
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_toolkit"),
    ]

    def build_toolkit(self) -> list[Tool]:
        from datetime import date

        client = LinkupClient(api_key=self.linkup_api_key)

        include_domains = None
        exclude_domains = None
        from_date = None
        to_date = None

        if self.from_date:
            with suppress(ValueError):
                from_date = date.fromisoformat(self.from_date)

        if self.to_date:
            with suppress(ValueError):
                to_date = date.fromisoformat(self.to_date)

        if self.include_domains:
            include_domains = [domain.strip() for domain in self.include_domains.split(",") if domain.strip()]

        if self.exclude_domains:
            exclude_domains = [domain.strip() for domain in self.exclude_domains.split(",") if domain.strip()]

        payload = {
            "depth": self.search_depth,
            "include_images": self.include_images,
        }

        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains
        if from_date:
            payload["from_date"] = from_date
        if to_date:
            payload["to_date"] = to_date

        @tool
        def sourced_with_sources(query: str):
            """Get search results with sources with a query."""
            return client.search(**payload, query=query, output_type="sourcedAnswer")

        @tool
        def search_results(query: str):
            """Get search results."""
            return client.search(**payload, query=query, output_type="searchResults")

        return [sourced_with_sources, search_results]

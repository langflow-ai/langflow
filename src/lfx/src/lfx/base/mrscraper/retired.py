"""MrScraper components retired in Langflow 1.13.0.

The MrScraper bundle now ships Account, Scraper API and Web Search. These classes keep the
inputs and outputs of the seven components it dropped, so a saved node still loads with its
fields and connections, and each output fails with a message that names the replacement.
They never import the MrScraper SDK.
"""

from typing import NoReturn

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class MrscraperRetiredError(RuntimeError):
    """A flow tried to run a MrScraper component retired in Langflow 1.13.0."""

    def __init__(self, display_name: str):
        """Name the retired component and its replacement."""
        super().__init__(
            f"{display_name} was retired in Langflow 1.13.0. Replace this node with MrScraper Scraper API "
            "and update the components that read its output."
        )


def _api_token_input() -> SecretStrInput:
    return SecretStrInput(
        name="api_token",
        display_name="MrScraper API Token",
        required=True,
        password=True,
        info="Your MrScraper API token. Get yours at https://app.mrscraper.com.",
    )


class RetiredMrscraperComponent(Component):
    """Shared attributes of the retired MrScraper components."""

    description: str = "Retired in Langflow 1.13.0. Replace this node with MrScraper Scraper API."
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"
    legacy = True
    retired_in = "1.13.0"
    replacement = ["mrscraper.MrscraperFetchHtml"]

    def _retired(self) -> NoReturn:
        raise MrscraperRetiredError(self.display_name)


class MrscraperAiScraper(RetiredMrscraperComponent):
    display_name: str = "MrScraper AI Agent Scraper"
    name = "MrscraperAiScraper"

    inputs = [
        _api_token_input(),
        MultilineInput(
            name="url",
            display_name="URL",
            required=True,
            info="Target URL to scrape.",
            tool_mode=True,
        ),
        MultilineInput(
            name="message",
            display_name="Extraction Prompt",
            required=True,
            info=(
                "Natural-language description of what to extract. "
                'Example: "Extract all product names, prices, and ratings".'
            ),
            tool_mode=True,
        ),
        DropdownInput(
            name="agent",
            display_name="Agent Type",
            options=["general", "listing", "map"],
            value="general",
            info=(
                '"general" works on almost any page. "listing" is optimised for listing/grid pages. '
                '"map agent" is optimised for map pages.'
            ),
        ),
        StrInput(
            name="proxy_country",
            display_name="Proxy Country",
            info='ISO country code for proxy geolocation (e.g. "us", "gb", "sg"). Optional.',
        ),
    ]

    outputs = [
        Output(display_name="Result", name="data", method="run_scraper"),
    ]

    async def run_scraper(self) -> Data:
        self._retired()


class MrscraperBatchScrape(RetiredMrscraperComponent):
    display_name: str = "MrScraper Batch Scrape URLs"
    name = "MrscraperBatchScrape"

    inputs = [
        _api_token_input(),
        StrInput(
            name="scraper_id",
            display_name="Scraper ID",
            required=True,
            info="ID of the scraper to rerun (from create_scraper or the MrScraper dashboard).",
            tool_mode=True,
        ),
        MultilineInput(
            name="urls",
            display_name="URLs",
            required=True,
            info="List of target URLs to scrape (separated by commas or new lines).",
            tool_mode=True,
        ),
        DropdownInput(
            name="mode",
            display_name="Scraper Mode",
            options=["AI", "Manual"],
            value="AI",
            info='"AI" uses bulk_rerun_ai_scraper. "Manual" uses bulk_rerun_manual_scraper.',
        ),
    ]

    outputs = [
        Output(display_name="Result", name="data", method="batch_scrape"),
    ]

    async def batch_scrape(self) -> Data:
        self._retired()


class MrscraperCrawlWebsite(RetiredMrscraperComponent):
    display_name: str = "MrScraper Crawl Website"
    name = "MrscraperCrawlWebsite"

    inputs = [
        _api_token_input(),
        MultilineInput(
            name="url",
            display_name="URL",
            required=True,
            info="Starting URL to crawl.",
            tool_mode=True,
        ),
        IntInput(
            name="max_depth",
            display_name="Max Depth",
            value=2,
            info="Crawl depth from the start URL. 0 = start URL only.",
        ),
        IntInput(
            name="max_pages",
            display_name="Max Pages",
            value=50,
            info="Maximum number of pages to process.",
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            value=1000,
            info="Maximum number of records to extract.",
        ),
        StrInput(
            name="include_patterns",
            display_name="Include Patterns",
            info='URL regex patterns to include when following links, separated by "||".',
            advanced=True,
        ),
        StrInput(
            name="exclude_patterns",
            display_name="Exclude Patterns",
            info='URL regex patterns to skip when following links, separated by "||".',
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="data", method="crawl"),
    ]

    async def crawl(self) -> Data:
        self._retired()


class MrscraperGetResult(RetiredMrscraperComponent):
    display_name: str = "MrScraper Get Result Detail"
    name = "MrscraperGetResult"

    inputs = [
        _api_token_input(),
        StrInput(
            name="result_id",
            display_name="Result ID",
            required=True,
            info="Unique identifier of the scraping result to retrieve.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="data", method="get_result"),
    ]

    async def get_result(self) -> Data:
        self._retired()


class MrscraperGetResults(RetiredMrscraperComponent):
    display_name: str = "MrScraper Get Results"
    name = "MrscraperGetResults"

    inputs = [
        _api_token_input(),
        DropdownInput(
            name="sort_field",
            display_name="Sort Field",
            options=[
                "createdAt",
                "updatedAt",
                "id",
                "type",
                "url",
                "status",
                "error",
                "tokenUsage",
                "runtime",
            ],
            value="updatedAt",
            info="Field to sort results by.",
            advanced=True,
        ),
        DropdownInput(
            name="sort_order",
            display_name="Sort Order",
            options=["ASC", "DESC"],
            value="DESC",
            info="Sort direction.",
            advanced=True,
        ),
        IntInput(
            name="page_size",
            display_name="Page Size",
            value=10,
            info="Number of results per page.",
        ),
        IntInput(
            name="page",
            display_name="Page",
            value=1,
            info="Page number (1-indexed).",
        ),
        StrInput(
            name="search",
            display_name="Search",
            info="Free-text search query across result fields. Optional.",
            advanced=True,
        ),
        StrInput(
            name="date_range_column",
            display_name="Date Range Column",
            info='Column to filter by date range (e.g. "updatedAt", "createdAt"). Optional.',
            advanced=True,
        ),
        StrInput(
            name="start_at",
            display_name="Start Date",
            info='ISO-8601 start date for the date range filter (e.g. "2024-01-01"). Optional.',
            advanced=True,
        ),
        StrInput(
            name="end_at",
            display_name="End Date",
            info='ISO-8601 end date for the date range filter (e.g. "2024-01-31"). Optional.',
            advanced=True,
        ),
    ]

    outputs = [
        # Output method names must not shadow Component.get_results() (build_output_logs).
        Output(display_name="Results", name="dataframe", method="fetch_all_results_as_dataframe"),
        Output(display_name="Raw Page", name="data", method="fetch_all_results"),
    ]

    async def fetch_all_results(self) -> Data:
        self._retired()

    async def fetch_all_results_as_dataframe(self) -> DataFrame:
        self._retired()


class MrscraperRunAiScraper(RetiredMrscraperComponent):
    display_name: str = "MrScraper Run AI Scraper"
    name = "MrscraperRunAiScraper"

    inputs = [
        _api_token_input(),
        StrInput(
            name="scraper_id",
            display_name="Scraper ID",
            required=True,
            info="ID of the AI scraper to rerun (from create_scraper).",
            tool_mode=True,
        ),
        MultilineInput(
            name="url",
            display_name="URL",
            required=True,
            info="Target URL. Can be the original URL or a different compatible page.",
            tool_mode=True,
        ),
        IntInput(
            name="max_depth",
            display_name="Max Depth",
            value=2,
            info="Crawl depth from the start URL (map agent only). 0 = start URL only.",
            advanced=True,
        ),
        IntInput(
            name="max_pages",
            display_name="Max Pages",
            value=50,
            info="Maximum pages to process (map agent only).",
            advanced=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            value=1000,
            info="Maximum records to extract (map agent only).",
            advanced=True,
        ),
        StrInput(
            name="include_patterns",
            display_name="Include Patterns",
            info="URL regex patterns to include when following links, separated by ||. (map agent only)",
            advanced=True,
        ),
        StrInput(
            name="exclude_patterns",
            display_name="Exclude Patterns",
            info="URL regex patterns to skip when following links, separated by ||. (map agent only)",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="data", method="rerun"),
    ]

    async def rerun(self) -> Data:
        self._retired()


class MrscraperRunManualScraper(RetiredMrscraperComponent):
    display_name: str = "MrScraper Run Manual Scraper"
    name = "MrscraperRunManualScraper"

    inputs = [
        _api_token_input(),
        StrInput(
            name="scraper_id",
            display_name="Scraper ID",
            required=True,
            info="ID of the manual scraper (from the MrScraper dashboard).",
            tool_mode=True,
        ),
        MultilineInput(
            name="url",
            display_name="URL",
            required=True,
            info="Target URL. The page structure should match the original scraper's target.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="data", method="rerun_manual"),
    ]

    async def rerun_manual(self) -> Data:
        self._retired()

"""MrScraper component: list and filter scraping results with pagination."""

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data


class MrscraperGetResults(Component):
    """Langflow component wrapping MrScraper `get_all_results` with sort and filters."""

    display_name: str = "MrScraper Get Results"
    description: str = "Retrieve a paginated, sortable, and filterable list of all MrScraper scraping results."
    name = "MrscraperGetResults"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [
        SecretStrInput(
            name="api_token",
            display_name="MrScraper API Token",
            required=True,
            password=True,
            info="Your MrScraper API token. Get yours at https://app.mrscraper.com.",
        ),
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
        # Output method name must not shadow Component.get_results() (build_output_logs).
        Output(display_name="Results", name="data", method="fetch_all_results"),
    ]

    async def fetch_all_results(self) -> Data:
        """Return a paginated list of results as `Data`."""
        try:
            from mrscraper import MrScraper
        except ImportError as e:
            msg = "Could not import mrscraper SDK. Please install it with `pip install mrscraper-sdk`."
            raise ImportError(msg) from e

        client = MrScraper(token=self.api_token)
        result = await client.get_all_results(
            sort_field=self.sort_field,
            sort_order=self.sort_order,
            page_size=self.page_size or 10,
            page=self.page or 1,
            search=self.search or None,
            date_range_column=self.date_range_column or None,
            start_at=self.start_at or None,
            end_at=self.end_at or None,
        )
        return Data(data=result)

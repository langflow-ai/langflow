"""MrScraper component: load a single scraping result by ID."""

from lfx.custom.custom_component.component import Component
from lfx.io import Output, SecretStrInput, StrInput
from lfx.schema.data import Data


class MrscraperGetResult(Component):
    """Langflow component wrapping MrScraper `get_result_by_id`."""

    display_name: str = "MrScraper Get Result Detail"
    description: str = "Retrieve the full details of a specific MrScraper scraping result by its ID."
    name = "MrscraperGetResult"
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
        """Return full detail for one result ID as `Data`."""
        try:
            from mrscraper import MrScraper
        except ImportError as e:
            msg = "Could not import mrscraper SDK. Please install it with `pip install mrscraper-sdk`."
            raise ImportError(msg) from e

        client = MrScraper(token=self.api_token)
        result = await client.get_result_by_id(result_id=self.result_id)
        return Data(data=result)

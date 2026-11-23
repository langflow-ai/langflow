"""MrScraper Status, retaining the existing MrscraperAccount identifier."""

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import api_token_input, call_sdk, payload


class MrscraperAccount(Component):
    """Return the raw account status API response through the SDK."""

    display_name: str = "MrScraper Status"
    description: str = (
        "Return the raw account status API response without summarizing, redacting body fields, "
        "or adding calculated fields."
    )
    name = "MrscraperAccount"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [api_token_input()]

    outputs = [Output(display_name="Account Status", name="data", method="get_account")]

    async def get_account(self) -> Data:
        """Fetch the account record for this token as the API sends it."""
        result = await call_sdk(self.api_token, "status")
        return Data(data=payload(result))

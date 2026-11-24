"""MrScraper component: account identity, subscription, and usage."""

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, Output, SecretStrInput
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import call_sdk, payload


class MrscraperAccount(Component):
    """Return the SDK's account summary without credentials or billing identifiers."""

    display_name: str = "MrScraper Account"
    description: str = "Check account identity, subscription status, token quota, and rate limits."
    name = "MrscraperAccount"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [
        SecretStrInput(
            name="api_token",
            display_name="MrScraper API Token",
            required=True,
            password=True,
            info="Your MrScraper API token from https://app.mrscraper.com.",
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=30.0,
            advanced=True,
            info="Positive HTTP request timeout in seconds.",
        ),
    ]

    outputs = [Output(display_name="Account", name="data", method="get_account")]

    async def get_account(self) -> Data:
        """Fetch a safe summary of this token's account."""
        result = await call_sdk(self.api_token, "account", timeout=self.timeout)
        return Data(data=payload(result))

from lfx.custom.custom_component.component import Component
from lfx.io import Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from .client import default_api_key, error_data, looot_request


class LoootGetBalanceComponent(Component):
    display_name = "looot Get Balance"
    description = "Read the prepaid balance left on your looot workspace. Free."
    documentation: str = "https://docs.looot.ai"
    icon = "Looot"
    name = "LoootGetBalanceComponent"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="looot API Key",
            info="Your looot API key. Create one at looot.ai. Defaults to the LOOOT_TOKEN environment variable.",
            value=default_api_key(),
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        try:
            await logger.ainfo("Reading the looot balance")
            response_data = await looot_request(self.api_key, "GET", "/v1/balance")
        except Exception as exc:  # noqa: BLE001
            await logger.aexception("looot balance failed")
            response_data = error_data(exc)

        self.status = response_data
        return Data(value=response_data)

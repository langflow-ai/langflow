from urllib.parse import quote

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from .client import default_api_key, error_data, looot_request


class LoootInspectEndpointComponent(Component):
    display_name = "looot Inspect Endpoint"
    description = "Read one looot endpoint's input fields, output shape and price before running it. Free."
    documentation: str = "https://docs.looot.ai"
    icon = "Looot"
    name = "LoootInspectEndpointComponent"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="looot API Key",
            info="Your looot API key. Create one at looot.ai. Defaults to the LOOOT_TOKEN environment variable.",
            value=default_api_key(),
            required=True,
        ),
        MessageTextInput(
            name="endpoint_id",
            display_name="Endpoint ID",
            info="An endpoint ID from a Search Catalog result, such as 'serper-search'.",
            value="",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        path = f"/v1/operations/{quote(self.endpoint_id.strip(), safe='')}"
        try:
            await logger.ainfo("Inspecting a looot endpoint")
            response_data = await looot_request(self.api_key, "GET", path)
        except Exception as exc:  # noqa: BLE001
            await logger.aexception("looot inspect failed")
            response_data = error_data(exc)

        self.status = response_data
        return Data(value=response_data)

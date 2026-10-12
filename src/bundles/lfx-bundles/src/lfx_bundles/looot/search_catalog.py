from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from .client import default_api_key, error_data, looot_request


class LoootSearchCatalogComponent(Component):
    display_name = "looot Search Catalog"
    description = "Search the looot data catalog in plain words and get ranked endpoints with their prices."
    documentation: str = "https://docs.looot.ai"
    icon = "Looot"
    name = "LoootSearchCatalogComponent"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="looot API Key",
            info="Your looot API key. Create one at looot.ai. Defaults to the LOOOT_TOKEN environment variable.",
            value=default_api_key(),
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="What you want to do, in plain words, such as 'find work email from name and company'.",
            value="",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info="Maximum number of endpoints to return.",
            value=20,
            advanced=True,
        ),
        DropdownInput(
            name="prefer",
            display_name="Prefer",
            info="How to rank results. Choose 'cheapest' to rank by price.",
            options=["balanced", "cheapest", "fastest", "reliable"],
            value="balanced",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        params: dict = {"q": self.query.strip(), "limit": self.limit, "prefer": self.prefer}
        try:
            await logger.ainfo("Searching the looot catalog")
            response_data = await looot_request(self.api_key, "GET", "/v1/catalog/search", params=params)
        except Exception as exc:  # noqa: BLE001
            await logger.aexception("looot catalog search failed")
            response_data = error_data(exc)

        self.status = response_data
        return Data(value=response_data)

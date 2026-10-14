from urllib.parse import quote

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from .client import default_api_key, error_data, looot_request


class LoootGetRunComponent(Component):
    display_name = "looot Get Run"
    description = (
        "Fetch a looot run by ID. Statuses queued, running, reconciliation_pending and "
        "pending_provider are not failures; poll again later."
    )
    documentation: str = "https://docs.looot.ai"
    icon = "Looot"
    name = "LoootGetRunComponent"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="looot API Key",
            info="Your looot API key. Create one at looot.ai. Defaults to the LOOOT_TOKEN environment variable.",
            value=default_api_key(),
            required=True,
        ),
        MessageTextInput(
            name="run_id",
            display_name="Run ID",
            info="The runId returned by Run Endpoint.",
            value="",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        path = f"/v1/runs/{quote(self.run_id.strip(), safe='')}"
        try:
            await logger.ainfo("Fetching a looot run")
            response_data = await looot_request(self.api_key, "GET", path)
        except Exception as exc:  # noqa: BLE001
            await logger.aexception("looot get run failed")
            response_data = error_data(exc)

        self.status = response_data
        return Data(value=response_data)

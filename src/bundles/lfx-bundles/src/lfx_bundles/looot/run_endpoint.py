import json
import uuid

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from .client import default_api_key, error_data, looot_request


class LoootRunEndpointComponent(Component):
    display_name = "looot Run Endpoint"
    description = (
        "Run one looot endpoint and pay per call from your prepaid balance. "
        "Inspect the endpoint first to see its price."
    )
    documentation: str = "https://docs.looot.ai"
    icon = "Looot"
    name = "LoootRunEndpointComponent"

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
        MultilineInput(
            name="input_json",
            display_name="Input (JSON)",
            info='The endpoint input as a JSON object, such as {"q": "coffee roasters berlin"}.',
            value="{}",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="idempotency_key",
            display_name="Idempotency Key",
            info=(
                "A unique key for this call. The same key with the same input never pays twice. "
                "Leave empty to use a new random key each run, which is not deduplicated."
            ),
            value="",
            advanced=True,
        ),
        IntInput(
            name="wait",
            display_name="Wait (seconds)",
            info="How long to wait for the result, from 0 to 60. 0 returns a run ID at once; use Get Run to poll it.",
            value=20,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def _parse_input(self) -> dict | None:
        """Return the input JSON as a dict, or None when it is not a JSON object."""
        try:
            payload = json.loads(self.input_json) if self.input_json.strip() else {}
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    async def build_output(self) -> Data:
        payload = self._parse_input()
        if payload is None:
            await logger.aerror("looot run input is not a JSON object")
            response_data = {"error": "Invalid input: Input (JSON) must be a JSON object"}
            self.status = response_data
            return Data(value=response_data)

        body = {
            "endpointId": self.endpoint_id.strip(),
            "input": payload,
            "idempotencyKey": self.idempotency_key.strip() or f"langflow-{uuid.uuid4()}",
        }
        wait = max(0, min(60, int(self.wait)))
        try:
            await logger.ainfo("Running a looot endpoint")
            response_data = await looot_request(self.api_key, "POST", "/v1/runs", params={"wait": wait}, json_body=body)
        except Exception as exc:  # noqa: BLE001
            await logger.aexception("looot run failed")
            response_data = error_data(exc)

        self.status = response_data
        return Data(value=response_data)

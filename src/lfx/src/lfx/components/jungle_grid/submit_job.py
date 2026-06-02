from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from ._client import JungleGridClient, build_workload_payload, optional_text, parse_json_field
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs, workload_inputs


class JungleGridSubmitJobComponent(Component):
    display_name = "Submit Job"
    description = "Submit a real Jungle Grid workload. This operation may start compute and consume credits."
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridSubmitJob"

    inputs = [
        *auth_inputs(),
        *workload_inputs(),
        StrInput(
            name="callback_url",
            display_name="Callback URL",
            advanced=True,
            info="Optional documented callback URL for job lifecycle notifications.",
        ),
        SecretStrInput(
            name="callback_auth_token",
            display_name="Callback Auth Token",
            advanced=True,
            password=True,
            info="Optional callback authentication token. This value is never logged by the component.",
        ),
        MultilineInput(
            name="callback_metadata",
            display_name="Callback Metadata JSON",
            advanced=True,
            info="Optional JSON object sent as documented callback metadata.",
        ),
    ]
    outputs = [Output(display_name="JSON", name="data", method="submit_job")]

    async def submit_job(self) -> Data:
        payload = build_workload_payload(
            name=self._attributes.get("name"),
            image=self.image,
            workload_type=self.workload_type,
            model_size_gb=self.model_size_gb,
            command=self.command,
            args=self.args,
            optimize_for=self.optimize_for,
        )
        if callback_url := optional_text(self.callback_url):
            payload["callback_url"] = callback_url
        if callback_auth_token := optional_text(self.callback_auth_token):
            payload["callback_auth_token"] = callback_auth_token
        if callback_metadata := parse_json_field(self.callback_metadata, "Callback Metadata", dict):
            payload["callback_metadata"] = callback_metadata

        client = JungleGridClient(self.api_key, self.api_base_url)
        result = await client.request("POST", "/v1/jobs", json_body=payload)
        data = Data(data=result)
        self.status = data
        return data

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data

from ._client import JungleGridClient, optional_text, path_segment
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs


class JungleGridCancelJobComponent(Component):
    display_name = "Cancel Job"
    description = (
        "Cancel a Jungle Grid job that has not reached a terminal state. "
        "This operation stops work where possible and is side-effecting."
    )
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridCancelJob"

    inputs = [
        *auth_inputs(),
        MessageTextInput(name="job_id", display_name="Job ID", required=True, tool_mode=True),
        MessageTextInput(name="reason", display_name="Reason", advanced=True, tool_mode=True),
    ]
    outputs = [Output(display_name="JSON", name="data", method="cancel_job")]

    async def cancel_job(self) -> Data:
        job_id = path_segment(self.job_id, "Job ID")
        payload = {}
        if reason := optional_text(self.reason):
            payload["reason"] = reason
        client = JungleGridClient(self.api_key, self.api_base_url)
        result = await client.request("POST", f"/v1/jobs/{job_id}/cancel", json_body=payload)
        data = Data(data=result)
        self.status = data
        return data

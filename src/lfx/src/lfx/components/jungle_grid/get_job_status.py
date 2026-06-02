from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data

from ._client import JungleGridClient, path_segment
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs


class JungleGridGetJobStatusComponent(Component):
    display_name = "Get Job Status"
    description = "Retrieve Jungle Grid job lifecycle status and details."
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridGetJobStatus"

    inputs = [
        *auth_inputs(),
        MessageTextInput(name="job_id", display_name="Job ID", required=True, tool_mode=True),
    ]
    outputs = [Output(display_name="JSON", name="data", method="get_job_status")]

    async def get_job_status(self) -> Data:
        job_id = path_segment(self.job_id, "Job ID")
        client = JungleGridClient(self.api_key, self.api_base_url)
        result = await client.request("GET", f"/v1/jobs/{job_id}")
        data = Data(data=result)
        self.status = data
        return data

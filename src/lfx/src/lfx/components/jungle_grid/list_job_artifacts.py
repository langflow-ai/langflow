from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data

from ._client import JungleGridClient, path_segment
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs


class JungleGridListJobArtifactsComponent(Component):
    display_name = "List Job Artifacts"
    description = (
        "List artifacts created by a Jungle Grid job. "
        "Artifacts may be unavailable until the job and storage processing complete."
    )
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridListJobArtifacts"

    inputs = [
        *auth_inputs(),
        MessageTextInput(name="job_id", display_name="Job ID", required=True, tool_mode=True),
    ]
    outputs = [Output(display_name="JSON", name="data", method="list_job_artifacts")]

    async def list_job_artifacts(self) -> Data:
        job_id = path_segment(self.job_id, "Job ID")
        client = JungleGridClient(self.api_key, self.api_base_url)
        result = await client.request("GET", f"/v1/jobs/{job_id}/artifacts")
        data = Data(data=result)
        self.status = data
        return data

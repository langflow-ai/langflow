from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data

from ._client import JungleGridClient, path_segment
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs


class JungleGridCreateArtifactDownloadURLComponent(Component):
    display_name = "Create Artifact Download URL"
    description = (
        "Create a temporary signed download URL for a Jungle Grid job artifact. "
        "Treat the returned URL as sensitive temporary output."
    )
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridCreateArtifactDownloadURL"

    inputs = [
        *auth_inputs(),
        MessageTextInput(name="job_id", display_name="Job ID", required=True, tool_mode=True),
        MessageTextInput(name="artifact_id", display_name="Artifact ID", required=True, tool_mode=True),
    ]
    outputs = [Output(display_name="JSON", name="data", method="create_artifact_download_url")]

    async def create_artifact_download_url(self) -> Data:
        job_id = path_segment(self.job_id, "Job ID")
        artifact_id = path_segment(self.artifact_id, "Artifact ID")
        client = JungleGridClient(self.api_key, self.api_base_url)
        result = await client.request("POST", f"/v1/jobs/{job_id}/artifacts/{artifact_id}/download", json_body={})
        data = Data(data=result)
        self.status = data
        return data

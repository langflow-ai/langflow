from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema.data import Data

from ._client import JungleGridClient
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs


class JungleGridListJobInputsComponent(Component):
    """List managed input and script uploads for the authenticated account."""

    display_name = "List Job Inputs"
    description = "List uploaded inputs and scripts, including readiness and managed mount paths."
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridListJobInputs"

    inputs = [*auth_inputs()]
    outputs = [Output(display_name="JSON", name="data", method="list_job_inputs")]

    async def list_job_inputs(self) -> Data:
        """Return the current account's managed job-input records."""
        result = await JungleGridClient(self.api_key, self.api_base_url).request("GET", "/v1/job-inputs")
        data = Data(data=result)
        self.status = data
        return data

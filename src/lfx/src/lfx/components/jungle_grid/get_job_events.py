from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data

from ._client import JungleGridClient, path_segment
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs


class JungleGridGetJobEventsComponent(Component):
    """Retrieve platform lifecycle events separately from workload logs."""

    display_name = "Get Job Events"
    description = (
        "Retrieve lifecycle events for capacity lookup, scheduling, provisioning, input preparation, container "
        "startup, retries, completion, failure, or cancellation. Events can exist before workload logs."
    )
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridGetJobEvents"

    inputs = [
        *auth_inputs(),
        MessageTextInput(name="job_id", display_name="Job ID", required=True, tool_mode=True),
    ]
    outputs = [Output(display_name="JSON", name="data", method="get_job_events")]

    async def get_job_events(self) -> Data:
        """Return ordered lifecycle events from the dedicated events endpoint."""
        job_id = path_segment(self.job_id, "Job ID")
        result = await JungleGridClient(self.api_key, self.api_base_url).request("GET", f"/v1/jobs/{job_id}/events")
        data = Data(data=result)
        self.status = data
        return data

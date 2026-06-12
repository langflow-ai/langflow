from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._client import JungleGridClient, normalize_workload_type, optional_text, validate_command, validate_string_array
from ._shared import (
    DOCUMENTATION_URL,
    ICON,
    args_input,
    auth_inputs,
    command_input,
    routing_mode_input,
    workload_type_input,
)


class JungleGridEstimateJobComponent(Component):
    """Estimate Jungle Grid routing, capacity, duration, and cost without submitting a job."""

    display_name = "Estimate Job"
    description = (
        "Estimate routing, capacity source, duration, and cost without submitting a job, starting compute, "
        "reserving capacity, or guaranteeing startup."
    )
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridEstimateJob"

    inputs = [
        *auth_inputs(),
        workload_type_input(),
        FloatInput(name="model_size", display_name="Model Size GB", advanced=True, tool_mode=True),
        MessageTextInput(name="image", display_name="Image", advanced=True, tool_mode=True),
        command_input(),
        args_input(),
        routing_mode_input(),
        MessageTextInput(name="template", display_name="Template", advanced=True, tool_mode=True),
        MessageTextInput(name="notes", display_name="Notes", advanced=True, tool_mode=True),
    ]
    outputs = [Output(display_name="JSON", name="data", method="estimate_job")]

    async def estimate_job(self) -> Data:
        """Call the read-only production estimate endpoint."""
        payload: dict = {"workload_type": normalize_workload_type(self.workload_type)}
        if self.model_size is not None:
            payload["model_size_gb"] = self.model_size
        if image := optional_text(self.image):
            payload["image"] = image
        command = validate_command(self.command)
        if command is not None:
            payload["command"] = command
        args = validate_string_array(self.args, "Args")
        if args is not None:
            payload["args"] = args
        if routing_mode := optional_text(self.routing_mode):
            payload["optimize_for"] = routing_mode
        if template := optional_text(self.template):
            payload["template"] = template
        if notes := optional_text(self.notes):
            payload["notes"] = notes

        result = await JungleGridClient(self.api_key, self.api_base_url).request(
            "POST", "/v1/mcp/jobs/estimate", json_body=payload
        )
        data = Data(data=result)
        self.status = data
        return data

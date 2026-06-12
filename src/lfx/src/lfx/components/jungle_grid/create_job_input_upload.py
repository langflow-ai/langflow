from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._client import JOB_INPUT_KINDS, JungleGridClient, JungleGridError, optional_text, require_text
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs


class JungleGridCreateJobInputUploadComponent(Component):
    """Create a temporary managed upload slot for a Jungle Grid input or script."""

    display_name = "Create Job Input Upload"
    description = (
        "Create a managed upload slot. This does not upload file bytes; PUT bytes to the temporary upload URL, "
        "then call the completion URL before submitting the input_id."
    )
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridCreateJobInputUpload"

    inputs = [
        *auth_inputs(),
        MessageTextInput(name="filename", display_name="Filename", required=True, tool_mode=True),
        MessageTextInput(name="content_type", display_name="Content Type", advanced=True, tool_mode=True),
        DropdownInput(
            name="kind",
            display_name="Kind",
            options=list(JOB_INPUT_KINDS),
            value="input",
            required=True,
            tool_mode=True,
        ),
    ]
    outputs = [Output(display_name="JSON", name="data", method="create_job_input_upload")]

    async def create_job_input_upload(self) -> Data:
        """Create an upload slot and keep its temporary credentials out of component status."""
        kind = require_text(self.kind, "Kind")
        if kind not in JOB_INPUT_KINDS:
            msg = f"Kind must be one of: {', '.join(JOB_INPUT_KINDS)}."
            raise JungleGridError(msg)
        payload = {"filename": require_text(self.filename, "Filename"), "kind": kind}
        if content_type := optional_text(self.content_type):
            payload["content_type"] = content_type
        result = await JungleGridClient(self.api_key, self.api_base_url).request(
            "POST", "/v1/job-inputs", json_body=payload
        )
        data = Data(data=result)
        self.status = Data(
            data={
                "summary": "Temporary job input upload information generated",
                "upload_url": "<redacted>",
                "complete_url": "<redacted>",
                "token": "<redacted>",
            }
        )
        return data

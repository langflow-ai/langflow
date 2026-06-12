from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.schema.data import Data

from ._client import (
    JungleGridClient,
    JungleGridError,
    normalize_workload_type,
    optional_text,
    parse_json_field,
    require_text,
    validate_command,
    validate_environment,
    validate_expected_artifacts,
    validate_input_references,
    validate_string_array,
)
from ._shared import (
    DOCUMENTATION_URL,
    ICON,
    args_input,
    auth_inputs,
    command_input,
    routing_mode_input,
    workload_type_input,
)


class JungleGridSubmitJobComponent(Component):
    """Submit a Jungle Grid workload using the current managed execution contract."""

    display_name = "Submit Job"
    description = "Submit a real Jungle Grid workload. This may start managed compute and consume credits."
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridSubmitJob"

    inputs = [
        *auth_inputs(),
        MessageTextInput(
            name="workload_name",
            display_name="Workload Name",
            required=True,
            tool_mode=True,
            info="Maps to the Jungle Grid API name field without colliding with the component identifier.",
        ),
        workload_type_input(),
        MessageTextInput(name="image", display_name="Image", required=True, tool_mode=True),
        command_input(),
        args_input(),
        MultilineInput(name="env", display_name="Environment JSON", advanced=True, tool_mode=True),
        MultilineInput(name="input_files", display_name="Input Files JSON", advanced=True, tool_mode=True),
        MultilineInput(name="script_files", display_name="Script Files JSON", advanced=True, tool_mode=True),
        MessageTextInput(
            name="script_file",
            display_name="Legacy Script Input ID",
            advanced=True,
            tool_mode=True,
            info="Deprecated compatibility alias for the first script_files input_id.",
        ),
        MultilineInput(
            name="expected_artifacts",
            display_name="Expected Artifacts JSON",
            advanced=True,
            tool_mode=True,
        ),
        routing_mode_input(),
        MessageTextInput(name="template", display_name="Template", advanced=True, tool_mode=True),
        MultilineInput(name="metadata", display_name="Metadata JSON", advanced=True, tool_mode=True),
        MessageTextInput(name="callback_url", display_name="Callback URL", advanced=True),
        SecretStrInput(name="callback_auth_token", display_name="Callback Auth Token", advanced=True, password=True),
        MultilineInput(name="callback_metadata", display_name="Callback Metadata JSON", advanced=True),
    ]
    outputs = [Output(display_name="JSON", name="data", method="submit_job")]

    async def submit_job(self) -> Data:
        """Validate and submit one workload without automatic retries."""
        legacy_name = self._attributes.get("name")
        workload_name = self._attributes.get("workload_name") or legacy_name
        legacy_workload = self._attributes.get("workload")
        workload_type = self._attributes.get("workload_type") or legacy_workload
        payload: dict = {
            "name": require_text(workload_name, "Workload Name"),
            "workload_type": normalize_workload_type(workload_type),
            "image": require_text(self.image, "Image"),
        }
        command = validate_command(self.command)
        if command is not None:
            payload["command"] = command
        args = validate_string_array(self.args, "Args")
        if args is not None:
            payload["args"] = args
        environment = validate_environment(self.env)
        if environment is not None:
            payload["environment"] = environment
        input_files = validate_input_references(self.input_files, "Input Files")
        if input_files is not None:
            payload["input_files"] = input_files
        script_files = validate_input_references(self.script_files, "Script Files")
        if script_files is not None:
            payload["script_files"] = script_files
        if script_file := optional_text(self.script_file):
            if "/" in script_file or "\\" in script_file:
                msg = "Legacy Script Input ID accepts a managed input ID, not a host filesystem path."
                raise JungleGridError(msg)
            payload["script_file"] = script_file
        expected_artifacts = validate_expected_artifacts(self.expected_artifacts)
        if expected_artifacts is not None:
            payload["expected_artifacts"] = expected_artifacts
        if routing_mode := optional_text(self.routing_mode):
            payload["optimize_for"] = routing_mode
        if template := optional_text(self.template):
            payload["template"] = template
        metadata = parse_json_field(self.metadata, "Metadata", dict)
        if metadata is not None:
            payload["metadata"] = metadata
        if callback_url := optional_text(self.callback_url):
            payload["callback_url"] = callback_url
        if callback_auth_token := optional_text(self.callback_auth_token):
            payload["callback_auth_token"] = callback_auth_token
        callback_metadata = parse_json_field(self.callback_metadata, "Callback Metadata", dict)
        if callback_metadata is not None:
            if any(not isinstance(value, str) for value in callback_metadata.values()):
                msg = "Callback Metadata must be a JSON object with string values."
                raise JungleGridError(msg)
            payload["callback_metadata"] = callback_metadata

        result = await JungleGridClient(self.api_key, self.api_base_url).request(
            "POST", "/v1/mcp/jobs", json_body=payload
        )
        data = Data(data=result)
        self.status = data
        return data

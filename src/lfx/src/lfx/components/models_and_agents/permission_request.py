import json

from lfx.custom import Component
from lfx.io import MultilineInput, Output
from lfx.schema.data import Data


class PermissionRequestComponent(Component):
    display_name = "Permission Request"
    description = "The tool name, arguments, and call identity supplied by the harness for a permission decision."
    icon = "ShieldQuestion"
    name = "PermissionRequest"
    inputs = [
        MultilineInput(
            name="sample_request",
            display_name="Preview request",
            value='{"tool_name":"example","args":{},"tool_call_id":"preview","approval_actions":[]}',
            info="Used for standalone previews. During an agent run the harness supplies the real tool call.",
        ),
    ]
    outputs = [Output(name="request", display_name="Request", method="build_request")]

    def build_request(self) -> Data:
        from lfx.projects.permissions import PERMISSION_INPUT

        request = (self.graph.context or {}).get(PERMISSION_INPUT) if self.graph else None
        if request is None:
            request = json.loads(self.sample_request)
        if not isinstance(request, dict):
            msg = "The permission request must be a JSON object."
            raise TypeError(msg)
        return Data(data=request)

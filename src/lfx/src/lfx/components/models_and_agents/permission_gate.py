from lfx.base.agents.permissions import Permission
from lfx.custom import Component
from lfx.io import DataInput, DropdownInput, MultilineInput, Output


class PermissionGateComponent(Component):
    display_name = "Permission Gate"
    description = "Approve, reject, or request review before a tool executes. Tool-specific approvals still apply."
    icon = "ShieldCheck"
    name = "PermissionGate"
    inputs = [
        DataInput(name="request", display_name="Request", required=True),
        DataInput(name="decision_data", display_name="Decision from a flow", required=False),
        DropdownInput(name="action", display_name="Action", options=["approve", "reject", "ask"], value="ask"),
        MultilineInput(name="reason", display_name="Reason", value=""),
    ]
    outputs = [Output(name="permission", display_name="Permission", method="build_permission")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_output = True

    def build_permission(self) -> Permission:
        result = (
            Permission.model_validate(self.decision_data.data)
            if self.decision_data is not None
            else Permission(action=self.action, reason=self.reason)
        )
        self.status = result.model_dump()
        return result

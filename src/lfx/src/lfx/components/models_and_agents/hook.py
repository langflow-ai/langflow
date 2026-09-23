import json

from lfx.base.agents.hooks import HookDecision
from lfx.custom import Component
from lfx.io import DataInput, DropdownInput, MultilineInput, Output


class HookComponent(Component):
    display_name = "Hook"
    description = "Return a hook decision. Connect logic that reads Hook Event, or configure a fixed decision."
    icon = "Webhook"
    name = "Hook"
    inputs = [
        DataInput(name="event", display_name="Event", required=True),
        DataInput(name="decision_data", display_name="Decision from a flow", required=False),
        DropdownInput(name="action", display_name="Action", options=["pass", "block", "modify"], value="pass"),
        MultilineInput(name="reason", display_name="Reason", value=""),
        MultilineInput(
            name="modified_payload",
            display_name="Changed fields (JSON)",
            value="{}",
            info="For modify: messages/tool_names before a model call, args before a tool, or result after a tool.",
        ),
    ]
    outputs = [Output(name="decision", display_name="Decision", method="build_decision")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_output = True

    def build_decision(self) -> HookDecision:
        if self.decision_data is not None:
            return HookDecision.model_validate(self.decision_data.data)
        return HookDecision(
            action=self.action,
            reason=self.reason,
            modified_payload=json.loads(self.modified_payload) if self.action == "modify" else None,
        )

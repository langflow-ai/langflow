import json

from lfx.custom import Component
from lfx.io import MultilineInput, Output
from lfx.schema.data import Data


class HookEventComponent(Component):
    display_name = "Hook Event"
    description = "The model or tool invocation supplied by the harness to this flow."
    icon = "Zap"
    name = "HookEvent"
    inputs = [
        MultilineInput(
            name="sample_event",
            display_name="Preview event",
            value='{"event":"before_tool_call","payload":{"tool_name":"example","args":{},"tool_call_id":"preview"}}',
            info="Used when running this flow on its own. The harness supplies the real event during an agent run.",
        ),
    ]
    outputs = [Output(name="event", display_name="Event", method="build_event")]

    def build_event(self) -> Data:
        from lfx.projects.hooks import HOOK_EVENT_CONTEXT

        event = (self.graph.context or {}).get(HOOK_EVENT_CONTEXT) if self.graph else None
        if event is None:
            event = json.loads(self.sample_event)
        if not isinstance(event, dict):
            msg = "The hook event must be a JSON object."
            raise TypeError(msg)
        return Data(data=event)

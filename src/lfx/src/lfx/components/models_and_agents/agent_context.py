import json

from lfx.custom import Component
from lfx.io import MultilineInput, Output
from lfx.schema.dataframe import DataFrame


class AgentContextComponent(Component):
    display_name = "Agent Context"
    description = "Messages supplied by the harness before a model call, after any compaction."
    icon = "MessagesSquare"
    name = "AgentContext"
    inputs = [
        MultilineInput(
            name="sample_messages",
            display_name="Preview messages",
            value='[{"type":"human","data":{"content":"Research this question using primary sources."}}]',
            info="Used only for standalone previews. Each record has type and data, preserving the complete message.",
        ),
    ]
    outputs = [Output(name="messages", display_name="Messages", method="build_messages")]

    def build_messages(self) -> DataFrame:
        from lfx.base.agents.context_messages import messages_from_rows, messages_to_table
        from lfx.projects.context import AGENT_CONTEXT

        context = (self.graph.context or {}).get(AGENT_CONTEXT) if self.graph else None
        rows = context["messages"] if context is not None else json.loads(self.sample_messages)
        return messages_to_table(messages_from_rows(rows))

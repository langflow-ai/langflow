from lfx.custom import Component
from lfx.io import DataFrameInput, DropdownInput, IntInput, Output
from lfx.schema.dataframe import DataFrame


class ContextManagerComponent(Component):
    display_name = "Prepare Context"
    description = "Return the messages for a model call. Stored conversation history stays intact."
    icon = "ListFilter"
    name = "ContextManager"
    inputs = [
        DataFrameInput(name="messages", display_name="Messages", required=True),
        DropdownInput(name="strategy", display_name="Keep", options=["all", "recent_turns"], value="all"),
        IntInput(name="turns", display_name="Recent complete turns", value=8, advanced=True),
    ]
    outputs = [Output(name="context", display_name="Messages", method="prepare_messages")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_output = True

    def prepare_messages(self) -> DataFrame:
        from lfx.base.agents.context_messages import messages_from_table, messages_to_table
        from lfx.base.agents.harness import HarnessRuntimeConfig
        from lfx.components.models_and_agents.agent_helpers.harness_middleware import prepare_context

        policy = HarnessRuntimeConfig(context_strategy=self.strategy, context_turns=self.turns)
        messages = messages_from_table(self.messages)
        prepared = (
            prepare_context(messages, policy.context_turns) if policy.context_strategy == "recent_turns" else messages
        )
        return messages_to_table(prepared)

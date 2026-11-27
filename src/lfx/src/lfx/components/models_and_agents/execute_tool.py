"""ExecuteTool: runs the tool calls the model asked for.

Takes the history from AgentStep. When it ends in an AI message with tool calls, it runs them in parallel through
the harness loop runtime and returns the history plus the tool results, which feed back to While Loop as the new
state. Any other history passes through unchanged.
"""

from __future__ import annotations

from langchain.agents.middleware import ToolRetryMiddleware
from langchain_core.messages import AIMessage, BaseMessage

from lfx.base.agents.loop_rows import messages_to_rows, rows_to_messages
from lfx.base.agents.loop_runtime import HarnessLoopRuntime
from lfx.components.models_and_agents.agent_helpers.loop_blocks import block_call, block_tools
from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, Output
from lfx.schema.dataframe import DataFrame


class ExecuteToolComponent(Component):
    display_name = "Execute Tool"
    description = "Run the tool calls the model asked for and return the history with the tool results."
    icon = "play"
    beta = True

    inputs = [
        HandleInput(
            name="messages",
            display_name="Messages",
            info="The history from Agent Step. Its tool calls run when it ends in an AI message that has some.",
            input_types=["DataFrame"],
            required=True,
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            info="The tools to run. Not needed when the loop runs inside a harness, which brings its own.",
            input_types=["Tool"],
            is_list=True,
            required=False,
        ),
    ]

    outputs = [Output(display_name="New Messages", name="new_messages", method="execute_tools")]

    def _own_runtime(self) -> HarnessLoopRuntime:
        # The model is never called here. A failing tool returns its error to the model, as in the Agent.
        return HarnessLoopRuntime(
            model=None,
            tools=block_tools(self.tools),
            system_prompt=None,
            middleware=[ToolRetryMiddleware(max_retries=0)],
        )

    async def execute_tools(self) -> DataFrame:
        history = rows_to_messages(self.messages)
        if not history or not isinstance(history[-1], AIMessage) or not history[-1].tool_calls:
            return self.messages

        async def run(runtime: HarnessLoopRuntime, messages: list[BaseMessage]) -> list[BaseMessage]:
            # A middleware that ended the run after the model asked for tools stops them here, as in create_agent.
            return [] if runtime.stopped else await runtime.tool_calls(messages[-1].tool_calls, messages)

        results, _ = await block_call(self, self._own_runtime, history, run)
        return DataFrame(messages_to_rows([*history, *results]))

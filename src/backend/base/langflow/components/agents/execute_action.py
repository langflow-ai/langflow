from typing import TYPE_CHECKING

from langflow.custom import Component
from langflow.io import HandleInput, Output
from langflow.schema.message import Message

if TYPE_CHECKING:
    from langchain_core.agents import AgentAction


class ExecuteActionComponent(Component):
    display_name = "Execute Action"
    description = "Executes the decided action using available tools."

    inputs = [
        HandleInput(name="agent_context", display_name="Agent Context", input_types=["AgentContext"], required=True),
    ]

    outputs = [Output(name="action_execution", display_name="Agent Context", method="execute_action")]

    def execute_action(self) -> Message:
        action: AgentAction = self.agent_context.last_action

        tools = self.agent_context.tools
        if action.tool in tools:
            data = tools[action.tool](action.tool_input)
            self.agent_context.last_action_result = data
            self.agent_context.update_context("Action Result", data)
        else:
            error_msg = f"Error: Action '{action}' not found in available tools."
            self.agent_context.last_action_result = error_msg
            self.agent_context.update_context("Action Result", error_msg)
        tool_call_result = f"Tool: {action.tool} called with input: {action.tool_input} and returned: {data.result}"
        self.status = self.agent_context.to_data_repr()
        return Message(text=tool_call_result)

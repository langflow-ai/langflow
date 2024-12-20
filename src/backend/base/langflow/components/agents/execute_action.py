from typing import TYPE_CHECKING, Any

from langflow.custom import Component
from langflow.io import Output
from langflow.schema.data import Data
from langflow.schema.message import Message

if TYPE_CHECKING:
    from langchain_core.agents import AgentAction


class ExecuteActionComponent(Component):
    display_name = "Execute Action"
    description = "Executes the selected action using available tools."

    outputs = [Output(name="action_result", display_name="Action Result", method="execute_action")]

    def _format_result(self, result: Any) -> str:
        if hasattr(result, "content"):
            return result.content
        if hasattr(result, "log"):
            return result.log
        return str(result)

    def execute_action(self) -> Message:
        # Get the action from context
        action: AgentAction = self.ctx.get("last_action")
        if not action:
            msg = "No action found in context to execute"
            raise ValueError(msg)

        # Get tools from context
        tools = self.ctx.get("tools", {})

        # Execute the action using the appropriate tool
        if action.tool in tools:
            result = tools[action.tool](action.tool_input)
            formatted_result = self._format_result(result)
            self.update_ctx({"last_action_result": formatted_result})
        else:
            error_msg = f"Action '{action}' not found in available tools."
            formatted_result = f"Error: {error_msg}"
            self.update_ctx({"last_action_result": formatted_result})

        # Create status data
        self.status = [
            Data(
                name="Action Execution",
                value=f"""
Tool: {action.tool}
Input: {action.tool_input}
Result: {formatted_result}
""",
            )
        ]

        return Message(text=formatted_result)

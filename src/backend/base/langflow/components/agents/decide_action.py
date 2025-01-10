from typing import TYPE_CHECKING

from langchain.agents.output_parsers.tools import parse_ai_message_to_tool_action

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.data import Data
from langflow.schema.message import Message

if TYPE_CHECKING:
    from langchain_core.messages import AIMessage


class DecideActionComponent(Component):
    display_name = "Decide Action"
    description = "Decides on an action based on the current thought and context."

    inputs = [
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            required=True,
            value="Based on your thought, decide the best action to take next.",
        ),
    ]

    outputs = [Output(name="action", display_name="Decided Action", method="decide_action")]

    def _format_context(self) -> str:
        ctx = self.ctx
        context_parts = []

        # Add current thought
        if ctx.get("thought"):
            context_parts.append(f"Current Thought: {ctx['thought']}")

        # Add available tools
        if "tools" in ctx:
            context_parts.append("\nAvailable Tools:")
            for tool_name, tool in ctx["tools"].items():
                context_parts.append(f"- {tool_name}: {tool.description}")

        return "\n".join(context_parts)

    def decide_action(self) -> Message:
        # Format the full context
        full_prompt = f"{self._format_context()}\n{self.prompt}\nAction:"

        # Generate action using LLM
        response: AIMessage = self.ctx["llm"].invoke(full_prompt)
        action = parse_ai_message_to_tool_action(response)

        # Handle action result and update context using update_ctx
        if isinstance(action, list):
            self.update_ctx({"last_action": action[0]})
            action = action[0]
        else:
            self.update_ctx({"last_action": action})

        # Create status data
        self.status = [
            Data(
                name="Decided Action",
                value=f"""
Context Used:
{self._format_context()}

Decided Action:
{action.log if hasattr(action, 'log') else str(action)}
""",
            )
        ]

        return Message(text=str(action))

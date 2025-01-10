from typing import TYPE_CHECKING

from langchain.agents.output_parsers.tools import parse_ai_message_to_tool_action

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.data import Data
from langflow.schema.message import Message

if TYPE_CHECKING:
    from langchain_core.messages import AIMessage


class GenerateThoughtComponent(Component):
    display_name = "Generate Thought"
    description = "Generates a thought based on the current context."

    inputs = [
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            required=True,
            value="Based on the provided context, generate your next thought.",
        ),
    ]

    outputs = [Output(name="thought", display_name="Generated Thought", method="generate_thought")]

    def _format_context(self) -> str:
        ctx = self.ctx
        context_parts = []

        # Add router decision if exists
        if "router_decision" in ctx:
            context_parts.append(f"Decision: {ctx['router_decision']}")

        # Add thought if exists
        if ctx.get("thought"):
            context_parts.append(f"Previous Thought: {ctx['thought']}")

        # Add last action and result if they exist
        if ctx.get("last_action"):
            context_parts.append(f"Last Action: {ctx['last_action']}")
            if ctx.get("last_action_result"):
                context_parts.append(f"Action Result: {ctx['last_action_result']}")

        # Add iteration info
        context_parts.append(f"Current Iteration: {ctx.get('iteration', 0)}/{ctx.get('max_iterations', 5)}")

        return "\n".join(context_parts)

    def generate_thought(self) -> Message:
        # Format the full context
        full_prompt = f"{self._format_context()}\n{self.prompt}\nThought:"

        # Generate thought using LLM
        thought: AIMessage = self.ctx["llm"].invoke(full_prompt)

        if not thought.content:
            action = parse_ai_message_to_tool_action(thought)
            if action:
                msg = (
                    "Invalid LLM response: An action was returned but no thought was generated. "
                    "The LLM should first generate a thought explaining its reasoning before taking any action. "
                    "Please check the prompt and LLM configuration. Maybe use a better model."
                )
                raise ValueError(msg)

        # Update context with new thought using update_ctx
        self.update_ctx({"thought": thought.content})

        # Create status data
        self.status = [
            Data(
                name="Generated Thought",
                value=f"""
Context Used:
{self._format_context()}

New Thought:
{thought.content}
""",
            )
        ]

        return Message(text=thought.content)

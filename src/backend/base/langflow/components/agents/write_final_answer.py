from typing import TYPE_CHECKING

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.data import Data
from langflow.schema.message import Message

if TYPE_CHECKING:
    from langchain_core.messages import AIMessage


class ProvideFinalAnswerComponent(Component):
    display_name = "Provide Final Answer"
    description = "Provides a final answer based on the context and actions taken."

    inputs = [
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            required=True,
            value="Considering all observations, provide the final answer to the user's query.",
        ),
    ]

    outputs = [Output(name="final_answer", display_name="Final Answer", method="get_final_answer")]

    def _format_context(self) -> str:
        ctx = self.ctx
        context_parts = []

        # Add thought if exists
        if ctx.get("thought"):
            context_parts.append(f"Last Thought: {ctx['thought']}")

        # Add last action and result if they exist
        if ctx.get("last_action"):
            context_parts.append(f"Last Action: {ctx['last_action']}")
            if ctx.get("last_action_result"):
                context_parts.append(f"Action Result: {ctx['last_action_result']}")

        # Add initial message for context
        if ctx.get("initial_message"):
            context_parts.append(f"\nInitial Query: {ctx['initial_message']}")

        return "\n".join(context_parts)

    def get_final_answer(self) -> Message:
        # Format the full context
        full_prompt = f"{self._format_context()}\n{self.prompt}\nFinal Answer:"

        # Generate final answer using LLM
        response: AIMessage = self.ctx["llm"].invoke(full_prompt)

        # Update context with final answer
        self.update_ctx({"final_answer": response.content})

        # Create status data
        self.status = [
            Data(
                name="Final Answer",
                value=f"""
Context Used:
{self._format_context()}

Final Answer:
{response.content}
""",
            )
        ]

        return Message(text=response.content)

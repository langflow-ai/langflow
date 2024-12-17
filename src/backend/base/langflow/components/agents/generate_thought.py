from typing import TYPE_CHECKING

from langflow.base.agents.context import AgentContext
from langflow.custom import Component
from langflow.io import HandleInput, MessageTextInput, Output

if TYPE_CHECKING:
    from langchain_core.messages import AIMessage


class GenerateThoughtComponent(Component):
    display_name = "Generate Thought"
    description = "Generates a thought based on the current context."

    inputs = [
        HandleInput(
            name="agent_context",
            display_name="Agent Context",
            input_types=["AgentContext"],
            required=True,
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            required=True,
            value="Based on the provided context, generate your next thought.",
        ),
    ]

    outputs = [Output(name="processed_agent_context", display_name="Agent Context", method="generate_thought")]

    def generate_thought(self) -> AgentContext:
        # Append the prompt after the accumulated context following ReAct format
        full_prompt = f"{self.agent_context.get_full_context()}\n{self.prompt}\nThought:"
        thought: AIMessage = self.agent_context.llm.invoke(full_prompt)
        self.agent_context.thought = thought
        self.agent_context.update_context("Thought", thought)
        self.status = self.agent_context.to_data_repr()
        return self.agent_context

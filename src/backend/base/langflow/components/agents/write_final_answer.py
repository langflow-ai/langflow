from typing import TYPE_CHECKING

from langflow.custom import Component
from langflow.io import HandleInput, MessageTextInput, Output
from langflow.schema.message import Message

if TYPE_CHECKING:
    from langchain_core.messages import AIMessage


class ProvideFinalAnswerComponent(Component):
    display_name = "Provide Final Answer"
    description = "Generates the final answer based on the agent's context."

    inputs = [
        HandleInput(name="agent_context", display_name="Agent Context", input_types=["AgentContext"], required=True),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            required=True,
            value="Considering all observations, provide the final answer to the user's query.",
        ),
    ]

    outputs = [Output(name="final_answer", method="get_final_answer")]

    def get_final_answer(self) -> Message:
        # Append the prompt after the accumulated context following ReAct format
        full_prompt = f"{self.agent_context.get_full_context()}\n{self.prompt}\nFinal Answer:"
        final_answer: AIMessage = self.agent_context.llm.invoke(full_prompt)
        self.agent_context.final_answer = final_answer
        self.agent_context.update_context("Final Answer", final_answer)
        self.status = self.agent_context.to_data_repr()
        return Message(text=final_answer.content)

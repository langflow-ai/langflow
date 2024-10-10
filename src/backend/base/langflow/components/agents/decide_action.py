from typing import TYPE_CHECKING

from langchain.agents.output_parsers.tools import parse_ai_message_to_tool_action

from langflow.base.agents.context import AgentContext
from langflow.custom import Component
from langflow.io import HandleInput, MessageTextInput, Output

if TYPE_CHECKING:
    from langchain_core.messages import AIMessage


class DecideActionComponent(Component):
    display_name = "Decide Action"
    description = "Decides on an action based on the current thought and context."

    inputs = [
        HandleInput(name="agent_context", display_name="Agent Context", input_types=["AgentContext"], required=True),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            required=True,
            value="Based on your thought, decide the best action to take next.",
        ),
    ]

    outputs = [Output(name="processed_agent_context", display_name="Agent Context", method="decide_action")]

    def decide_action(self) -> AgentContext:
        # Append the prompt after the accumulated context following ReAct format
        full_prompt = f"{self.agent_context.get_full_context()}\n{self.prompt}\nAction:"
        response: AIMessage = self.agent_context.llm.invoke(full_prompt)
        action = parse_ai_message_to_tool_action(response)
        self.agent_context.last_action = action[0]
        self.agent_context.update_context("Action", action)
        self.status = self.agent_context.to_data_repr()
        return self.agent_context

from langflow.base.agents.context import AgentContext
from langflow.custom import Component
from langflow.io import HandleInput, MessageTextInput, Output


class ObserveResultComponent(Component):
    display_name = "Observe Result"
    description = "Observes and processes the result of the executed action."

    inputs = [
        HandleInput(name="agent_context", display_name="Agent Context", input_types=["AgentContext"], required=True),
        MessageTextInput(name="prompt", display_name="Prompt", required=True),
    ]

    outputs = [Output(name="observation", display_name="Observation", method="observe_result")]

    def observe_result(self) -> AgentContext:
        # Move the prompt to the end of the context
        full_prompt = f"{self.agent_context.get_full_context()}\n{self.prompt}"
        observation = self.agent_context.llm.invoke(full_prompt)
        self.agent_context.update_context(f"Observation: {observation}")
        return self.agent_context

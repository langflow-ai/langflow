from langflow.base.agents.context import AgentContext
from langflow.custom import Component
from langflow.io import HandleInput, MessageTextInput, Output


class ObserveResultComponent(Component):
    display_name = "Observe Result"
    description = "Observes and processes the result of the executed action."

    inputs = [
        HandleInput(name="agent_context", input_types=["AgentContext"], required=True),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            required=True,
            value="Analyze the result of the action and provide an observation.",
        ),
    ]

    outputs = [Output(name="agent_context", method="observe_result")]

    def observe_result(self) -> AgentContext:
        # Append the prompt after the accumulated context following ReAct format
        full_prompt = f"{self.agent_context.get_full_context()}\n{self.prompt}\nObservation:"
        observation = self.agent_context.llm.invoke(full_prompt).strip()
        self.agent_context.update_context("Observation", observation)
        return self.agent_context

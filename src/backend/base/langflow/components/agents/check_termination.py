from langflow.base.agents.context import AgentContext
from langflow.custom import Component
from langflow.io import HandleInput, Output


class CheckTerminationComponent(Component):
    display_name = "Check Termination"
    description = "Checks if the agent should terminate or continue the loop."

    inputs = [
        HandleInput(name="agent_context", input_types=["AgentContext"], required=True),
    ]

    outputs = [
        Output(name="agent_context", method="check_termination"),
    ]

    def check_termination(self) -> AgentContext:
        should_continue = (
            self.agent_context.iteration < self.agent_context.max_iterations
            and not self.agent_context.llm.should_terminate(self.agent_context.context)
        )
        return should_continue, self.agent_context

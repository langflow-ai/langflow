from langchain.schema.agent import AgentFinish

from langflow.base.agents.context import AgentContext
from langflow.custom import Component
from langflow.io import HandleInput, IntInput, Output


class AgentActionRouter(Component):
    display_name = "Agent Action Router"
    description = "Routes the agent's flow based on the last action type."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__iteration_updated = False

    inputs = [
        HandleInput(name="agent_context", display_name="Agent Context", input_types=["AgentContext"], required=True),
        IntInput(name="max_iterations", display_name="Max Interations", required=True, value=5),
    ]

    outputs = [
        Output(name="execute_tool", display_name="Execute Tool", method="route_to_execute_tool", cache=False),
        Output(name="final_answer", display_name="Final Answer", method="route_to_final_answer", cache=False),
    ]

    def _pre_run_setup(self):
        self.__iteration_updated = False

    def _get_context_message_and_route_to_stop(self) -> tuple[str, str]:
        if (
            isinstance(self.agent_context.last_action, AgentFinish)
            or self.agent_context.iteration >= self.agent_context.max_iterations
        ):
            return "Provide Final Answer", "execute_tool"
        return "Execute Tool", "final_answer"

    def iterate_and_stop_once(self, route_to_stop: str):
        if not self.__iteration_updated:
            self.agent_context.iteration += 1
            self.__iteration_updated = True
            self.stop(route_to_stop)

    def route_to_execute_tool(self) -> AgentContext:
        context_message, route_to_stop = self._get_context_message_and_route_to_stop()
        self.agent_context.update_context("Router Decision", context_message)
        self.iterate_and_stop_once(route_to_stop)
        self.status = self.agent_context.to_data_repr()
        return self.agent_context

    def route_to_final_answer(self) -> AgentContext:
        context_message, route_to_stop = self._get_context_message_and_route_to_stop()
        self.agent_context.update_context("Router Decision", context_message)
        self.iterate_and_stop_once(route_to_stop)
        self.status = self.agent_context.to_data_repr()
        return self.agent_context

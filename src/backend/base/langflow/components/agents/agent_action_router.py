from langchain.schema.agent import AgentFinish

from langflow.custom import Component
from langflow.io import IntInput, Output
from langflow.schema.data import Data
from langflow.schema.message import Message


class AgentActionRouter(Component):
    display_name = "Agent Action Router"
    description = "Routes the agent's flow based on the last action type."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__iteration_updated = False

    inputs = [
        IntInput(name="max_iterations", display_name="Max Iterations", required=True, value=5),
    ]

    outputs = [
        Output(name="execute_tool", display_name="Execute Tool", method="route_to_execute_tool", cache=False),
        Output(name="final_answer", display_name="Final Answer", method="route_to_final_answer", cache=False),
    ]

    def _pre_run_setup(self):
        self.__iteration_updated = False
        # Initialize context if not already set
        if "iteration" not in self.ctx:
            self.update_ctx(
                {
                    "iteration": 0,
                    "max_iterations": self.max_iterations,
                    "thought": "",
                    "last_action": None,
                    "last_action_result": None,
                    "final_answer": "",
                }
            )

    def _get_context_message_and_route_to_stop(self) -> tuple[str, str]:
        ctx = self.ctx
        if isinstance(ctx.get("last_action"), AgentFinish) or ctx.get("iteration", 0) >= ctx.get(
            "max_iterations", self.max_iterations
        ):
            return "Provide Final Answer", "execute_tool"
        return "Execute Tool", "final_answer"

    def iterate_and_stop_once(self, route_to_stop: str):
        if not self.__iteration_updated:
            current_iteration = self.ctx.get("iteration", 0)
            self.update_ctx({"iteration": current_iteration + 1})
            self.__iteration_updated = True
            self.stop(route_to_stop)

    def _create_status_data(self) -> list[Data]:
        ctx = self.ctx
        return [
            Data(
                name="Agent State",
                value=f"""
Iteration: {ctx.get('iteration', 0)}
Last Action: {ctx.get('last_action')}
Last Result: {ctx.get('last_action_result')}
Thought: {ctx.get('thought', '')}
Final Answer: {ctx.get('final_answer', '')}
""",
            )
        ]

    def route_to_execute_tool(self) -> Message:
        context_message, route_to_stop = self._get_context_message_and_route_to_stop()
        self.update_ctx({"router_decision": context_message})
        self.iterate_and_stop_once(route_to_stop)
        self.status = self._create_status_data()
        return Message(text=context_message, type="routing_decision")

    def route_to_final_answer(self) -> Message:
        context_message, route_to_stop = self._get_context_message_and_route_to_stop()
        self.update_ctx({"router_decision": context_message})
        self.iterate_and_stop_once(route_to_stop)
        self.status = self._create_status_data()
        return Message(text=context_message, type="routing_decision")

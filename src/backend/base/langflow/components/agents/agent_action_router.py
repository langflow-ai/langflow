from langchain.schema.agent import AgentAction, AgentFinish

from langflow.base.agents.context import AgentContext
from langflow.custom import Component
from langflow.io import HandleInput, Output


class AgentActionRouter(Component):
    display_name = "Agent Action Router"
    description = "Routes the agent's flow based on the last action type."

    inputs = [
        HandleInput(name="agent_context", display_name="Agent Context", input_types=["AgentContext"], required=True),
    ]

    outputs = [
        Output(name="execute_tool", display_name="Execute Tool", method="route_to_execute_tool"),
        Output(name="final_answer", display_name="Final Answer", method="route_to_final_answer"),
    ]

    def route_to_execute_tool(self) -> AgentContext:
        if isinstance(self.agent_context.last_action, AgentAction):
            self.agent_context.update_context("Router Decision", "Execute Tool")
            self.stop("final_answer")
            self.status = self.agent_context.to_data_repr()
            return self.agent_context
        self.stop("execute_tool")
        self.status = self.agent_context.to_data_repr()
        return None

    def route_to_final_answer(self) -> AgentContext:
        if isinstance(self.agent_context.last_action, AgentFinish):
            self.agent_context.update_context("Router Decision", "Provide Final Answer")
            self.stop("execute_tool")
            self.status = self.agent_context.to_data_repr()
            return self.agent_context
        self.stop("final_answer")
        self.status = self.agent_context.to_data_repr()
        return None

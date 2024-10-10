from langflow.base.agents.context import AgentContext
from langflow.custom import Component
from langflow.io import HandleInput, IntInput, MessageTextInput, Output


class AgentContextBuilder(Component):
    display_name = "Agent Context Builder"
    description = "Builds the AgentContext instance for the agent execution loop."

    inputs = [
        HandleInput(name="tools", display_name="Tools", input_types=["Tool"], is_list=True, required=True),
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
        MessageTextInput(name="initial_context", display_name="Initial Context", required=False),
        IntInput(name="max_iterations", display_name="Max Iterations", value=5, required=False),
    ]

    outputs = [Output(name="agent_context", display_name="Agent Context", method="build_context")]

    def build_context(self) -> AgentContext:
        tools_dict = {tool.name: tool for tool in self.tools}
        context = AgentContext(tools=tools_dict, llm=self.llm, context=self.initial_context or "", iteration=0)
        if self.max_iterations is not None:
            context.max_iterations = self.max_iterations
        self.status = context.to_data_repr()
        return context

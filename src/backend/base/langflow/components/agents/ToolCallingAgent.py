from langchain.agents import create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate, HumanMessagePromptTemplate
from langflow.base.agents.agent import LCToolsAgentComponent
from langflow.inputs import MultilineInput


class ToolCallingAgentComponent(LCToolsAgentComponent):
    display_name: str = "Tool Calling Agent"
    description: str = "Agent that uses tools"
    icon = "LangChain"
    beta = True
    name = "ToolCallingAgent"

    inputs = LCToolsAgentComponent._base_inputs + [
        MultilineInput(
            name="system_prompt",
            display_name="System Prompt",
            info="System prompt for the agent.",
            value="You are a helpful assistant",
        ),
        MultilineInput(
            name="user_prompt", display_name="Prompt", info="This prompt must contain 'input' key.", value="{input}"
        ),
    ]

    def creat_agent_runnable(self):
        if "input" not in self.user_prompt:
            raise ValueError("Prompt must contain 'input' key.")
        messages = [
            ("system", self.system_prompt),
            HumanMessagePromptTemplate(prompt=PromptTemplate(input_variables=["input"], template=self.user_prompt)),
            ("placeholder", "{agent_scratchpad}"),
        ]
        prompt = ChatPromptTemplate.from_messages(messages)
        return create_tool_calling_agent(self.llm, self.tools, prompt)

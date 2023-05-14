from langchain import LLMChain
from langchain.agents import AgentExecutor, ZeroShotAgent
from langchain.agents.agent_toolkits.json.prompt import JSON_PREFIX, JSON_SUFFIX
from langchain.agents.agent_toolkits.json.toolkit import JsonToolkit
from langchain.agents.mrkl.prompt import FORMAT_INSTRUCTIONS
from langchain.base_language import BaseLanguageModel


class MalfoyAgent(AgentExecutor):
    """Json agent"""

    prefix = "Malfoy: "

    @classmethod
    def initialize(cls, *args, **kwargs):
        return cls.from_toolkit_and_llm(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_toolkit_and_llm(cls, toolkit: JsonToolkit, llm: BaseLanguageModel):
        tools = toolkit.get_tools()
        tool_names = {tool.name for tool in tools}
        prompt = ZeroShotAgent.create_prompt(
            tools,
            prefix=JSON_PREFIX,
            suffix=JSON_SUFFIX,
            format_instructions=FORMAT_INSTRUCTIONS,
            input_variables=None,
        )
        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
        )
        agent = ZeroShotAgent(llm_chain=llm_chain, allowed_tools=tool_names)  # type: ignore
        return cls.from_agent_and_tools(agent=agent, tools=tools, verbose=True)

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)


PREBUILT_AGENTS = {
    "MalfoyAgent": MalfoyAgent,
}

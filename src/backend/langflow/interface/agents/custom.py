from langchain import LLMChain
from langchain.agents import AgentExecutor, ZeroShotAgent
from langchain.agents.agent_toolkits.json.prompt import JSON_PREFIX, JSON_SUFFIX
from langchain.agents.agent_toolkits.json.toolkit import JsonToolkit
from langchain.agents.mrkl.prompt import FORMAT_INSTRUCTIONS
from langchain.schema import BaseLanguageModel
from pydantic import BaseModel


class JsonAgent(BaseModel):
    """Json agent"""

    toolkit: JsonToolkit
    llm: BaseLanguageModel

    def __init__(self, toolkit: JsonToolkit, llm: BaseLanguageModel):
        super().__init__(toolkit=toolkit, llm=llm)
        self.toolkit = toolkit
        tools = self.toolkit.get_tools()
        tool_names = [tool.name for tool in tools]
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
        agent = ZeroShotAgent(llm_chain=llm_chain, allowed_tools=tool_names)
        self.agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent, tools=tools, verbose=True
        )

    def __call__(self, *args, **kwargs):
        return self.agent_executor(*args, **kwargs)

    def run(self, *args, **kwargs):
        return self.agent_executor.run(*args, **kwargs)

from typing import Any, List, Optional

from langchain import LLMChain
from langchain.agents import AgentExecutor, Tool, ZeroShotAgent, initialize_agent
from langchain.agents.agent_toolkits.json.prompt import JSON_PREFIX, JSON_SUFFIX
from langchain.agents.agent_toolkits.json.toolkit import JsonToolkit
from langchain.agents.agent_toolkits.pandas.prompt import PREFIX as PANDAS_PREFIX
from langchain.agents.agent_toolkits.pandas.prompt import SUFFIX as PANDAS_SUFFIX
from langchain.agents.mrkl.prompt import FORMAT_INSTRUCTIONS
from langchain.llms.base import BaseLLM
from langchain.memory.chat_memory import BaseChatMemory
from langchain.schema import BaseLanguageModel
from langchain.tools.python.tool import PythonAstREPLTool


class JsonAgent(AgentExecutor):
    """Json agent"""

    @staticmethod
    def function_name():
        return "JsonAgent"

    @classmethod
    def initialize(cls, *args, **kwargs):
        return cls.from_toolkit_and_llm(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_toolkit_and_llm(cls, toolkit: JsonToolkit, llm: BaseLanguageModel):
        tools = toolkit.get_tools()
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
        return cls.from_agent_and_tools(agent=agent, tools=tools, verbose=True)

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)


class CSVAgent(AgentExecutor):
    """CSV agent"""

    @staticmethod
    def function_name():
        return "CSVAgent"

    @classmethod
    def initialize(cls, *args, **kwargs):
        return cls.from_toolkit_and_llm(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_toolkit_and_llm(
        cls,
        path: dict,
        llm: BaseLanguageModel,
        pandas_kwargs: Optional[dict] = None,
        **kwargs: Any
    ):
        import pandas as pd  # type: ignore

        _kwargs = pandas_kwargs or {}
        df = pd.DataFrame.from_dict(path, **_kwargs)

        tools = [PythonAstREPLTool(locals={"df": df})]  # type: ignore
        prompt = ZeroShotAgent.create_prompt(
            tools,
            prefix=PANDAS_PREFIX,
            suffix=PANDAS_SUFFIX,
            input_variables=["df", "input", "agent_scratchpad"],
        )
        partial_prompt = prompt.partial(df=str(df.head()))
        llm_chain = LLMChain(
            llm=llm,
            prompt=partial_prompt,
        )
        tool_names = [tool.name for tool in tools]
        agent = ZeroShotAgent(llm_chain=llm_chain, allowed_tools=tool_names, **kwargs)

        return cls.from_agent_and_tools(agent=agent, tools=tools, verbose=True)

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)


class InitializeAgent(AgentExecutor):
    """Implementation of initialize_agent function"""

    @staticmethod
    def function_name():
        return "initialize_agent"

    @classmethod
    def initialize(
        cls, llm: BaseLLM, tools: List[Tool], agent: str, memory: BaseChatMemory
    ):
        return initialize_agent(
            tools=tools,
            llm=llm,
            # LangChain now uses Enum for agent, but we still support string
            agent=agent,  # type: ignore
            memory=memory,
            return_intermediate_steps=True,
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)


CUSTOM_AGENTS = {
    "JsonAgent": JsonAgent,
    "CSVAgent": CSVAgent,
    "initialize_agent": InitializeAgent,
}

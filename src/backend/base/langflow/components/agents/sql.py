from langchain.agents import AgentExecutor
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.utilities import SQLDatabase

from langflow.base.agents.agent import LCAgentComponent
from langflow.inputs import HandleInput, MessageTextInput


class SQLAgentComponent(LCAgentComponent):
    display_name = "SQLAgent"
    description = "Construct an SQL agent from an LLM and tools."
    name = "SQLAgent"

    inputs = [
        *LCAgentComponent._base_inputs,
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
        MessageTextInput(name="database_uri", display_name="Database URI", required=True),
        HandleInput(
            name="extra_tools",
            display_name="Extra Tools",
            input_types=["Tool", "BaseTool"],
            is_list=True,
            advanced=True,
        ),
    ]

    def build_agent(self) -> AgentExecutor:
        db = SQLDatabase.from_uri(self.database_uri)
        toolkit = SQLDatabaseToolkit(db=db, llm=self.llm)
        agent_args = self.get_agent_kwargs()
        agent_args["max_iterations"] = agent_args["agent_executor_kwargs"]["max_iterations"]
        del agent_args["agent_executor_kwargs"]["max_iterations"]
        return create_sql_agent(llm=self.llm, toolkit=toolkit, extra_tools=self.extra_tools or [], **agent_args)

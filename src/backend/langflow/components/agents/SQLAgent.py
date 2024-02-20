from langflow import CustomComponent
from typing import Union, Callable
from langchain.agents import AgentExecutor
from langflow.field_typing import BaseLanguageModel
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain.sql_database import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit


class SQLAgentComponent(CustomComponent):
    display_name = "SQLAgent"
    description = "Construct an SQL agent from an LLM and tools."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "database_uri": {"display_name": "Database URI"},
            "verbose": {"display_name": "Verbose", "value": False, "advanced": True},
        }

    def build(
        self,
        llm: BaseLanguageModel,
        database_uri: str,
        verbose: bool = False,
    ) -> Union[AgentExecutor, Callable]:
        db = SQLDatabase.from_uri(database_uri)
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        return create_sql_agent(llm=llm, toolkit=toolkit)

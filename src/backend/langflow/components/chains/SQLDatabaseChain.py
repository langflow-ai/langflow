from langflow import CustomComponent
from typing import Callable, Union
from langflow.field_typing import BasePromptTemplate, BaseLanguageModel, Chain
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_experimental.sql.base import SQLDatabaseChain


class SQLDatabaseChainComponent(CustomComponent):
    display_name = "SQLDatabaseChain"
    description = ""

    def build_config(self):
        return {
            "db": {"display_name": "Database"},
            "llm": {"display_name": "LLM"},
            "prompt": {"display_name": "Prompt"},
        }

    def build(
        self,
        db: SQLDatabase,
        llm: BaseLanguageModel,
        prompt: BasePromptTemplate,
    ) -> Union[Chain, Callable, SQLDatabaseChain]:
        return SQLDatabaseChain.from_llm(llm=llm, db=db, prompt=prompt)

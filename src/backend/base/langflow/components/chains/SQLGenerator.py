from typing import Optional

from langchain.chains import create_sql_query_chain
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import Runnable

from langflow.field_typing import BaseLanguageModel, Text
from langflow.interface.custom.custom_component import CustomComponent


class SQLGeneratorComponent(CustomComponent):
    display_name = "Natural Language to SQL"
    description = "Generate SQL from natural language."

    def build_config(self):
        return {
            "db": {"display_name": "Database"},
            "llm": {"display_name": "LLM"},
            "prompt": {
                "display_name": "Prompt",
                "info": "The prompt must contain `{question}`.",
            },
            "top_k": {
                "display_name": "Top K",
                "info": "The number of results per select statement to return. If 0, no limit.",
            },
            "input_value": {
                "display_name": "Input Value",
                "info": "The input value to pass to the chain.",
            },
        }

    def build(
        self,
        input_value: Text,
        db: SQLDatabase,
        llm: BaseLanguageModel,
        top_k: int = 5,
        prompt: Optional[Text] = None,
    ) -> Text:
        if prompt:
            prompt_template = PromptTemplate.from_template(template=prompt)
        else:
            prompt_template = None

        if top_k < 1:
            raise ValueError("Top K must be greater than 0.")

        if not prompt_template:
            sql_query_chain = create_sql_query_chain(llm=llm, db=db, k=top_k)
        else:
            # Check if {question} is in the prompt
            if "{question}" not in prompt_template.template or "question" not in prompt_template.input_variables:
                raise ValueError("Prompt must contain `{question}` to be used with Natural Language to SQL.")
            sql_query_chain = create_sql_query_chain(llm=llm, db=db, prompt=prompt_template, k=top_k)
        query_writer: Runnable = sql_query_chain | {"query": lambda x: x.replace("SQLQuery:", "").strip()}
        response = query_writer.invoke({"question": input_value})
        query = response.get("query")
        self.status = query
        return query

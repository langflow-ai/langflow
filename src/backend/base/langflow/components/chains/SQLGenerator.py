from langchain.chains import create_sql_query_chain
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import Runnable
from langflow.base.chains.model import LCChainComponent
from langflow.field_typing import Message
from langflow.inputs import MultilineInput, HandleInput, IntInput
from langflow.template import Output


class SQLGeneratorComponent(LCChainComponent):
    display_name = "Natural Language to SQL"
    description = "Generate SQL from natural language."
    name = "SQLGenerator"

    inputs = [
        MultilineInput(
            name="input_value", display_name="Input", info="The input value to pass to the chain.", required=True
        ),
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
        HandleInput(name="db", display_name="SQLDatabase", input_types=["SQLDatabase"], required=True),
        IntInput(
            name="top_k", display_name="Top K", info="The number of results per select statement to return.", value=5
        ),
        MultilineInput(name="prompt", display_name="Prompt", info="The prompt must contain `{question}`."),
    ]

    outputs = [Output(display_name="Text", name="text", method="invoke_chain")]

    def invoke_chain(self) -> Message:
        if self.prompt:
            prompt_template = PromptTemplate.from_template(template=self.prompt)
        else:
            prompt_template = None

        if self.top_k < 1:
            raise ValueError("Top K must be greater than 0.")

        if not prompt_template:
            sql_query_chain = create_sql_query_chain(llm=self.llm, db=self.db, k=self.top_k)
        else:
            # Check if {question} is in the prompt
            if "{question}" not in prompt_template.template or "question" not in prompt_template.input_variables:
                raise ValueError("Prompt must contain `{question}` to be used with Natural Language to SQL.")
            sql_query_chain = create_sql_query_chain(llm=self.llm, db=self.db, prompt=prompt_template, k=self.top_k)
        query_writer: Runnable = sql_query_chain | {"query": lambda x: x.replace("SQLQuery:", "").strip()}
        response = query_writer.invoke({"question": self.input_value})
        query = response.get("query")
        self.status = query
        return query

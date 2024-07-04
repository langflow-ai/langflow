# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.io import Output, TextInput, StrInput, HandleInput

from langchain.utils.math import cosine_similarity
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough


class RoutedPrompt(Component):
    display_name = "RoutedPrompt"
    description = "Use embeddings to route a query to the most relevant prompt."
    documentation: str = (
        "https://python.langchain.com/v0.1/docs/expression_language/how_to/routing/#using-a-custom-function-recommended"
    )
    icon = "custom_components"

    inputs = [
        TextInput(name="input_value", display_name="Input Value", value="Hello, World!"),
        StrInput(
            name="prompt_templates",
            display_name="Prompt templates",
            is_list=True,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        HandleInput(
            name="llm",
            display_name="LLM",
            input_types=["LanguageModel"],
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def _prompt_router(self, input, embeddings, prompt_templates, prompt_embeddings):
        query_embedding = embeddings.embed_query(input["query"])
        similarity = cosine_similarity([query_embedding], prompt_embeddings)[0]
        most_similar = prompt_templates[similarity.argmax()]
        return PromptTemplate.from_template(most_similar)

    def build_output(self) -> Text:
        if not isinstance(self.prompt_templates, list):
            self.status = ""
            return
        prompt_embeddings = self.embedding.embed_documents(self.prompt_templates)
        chain = (
            {"query": RunnablePassthrough()}
            | RunnableLambda(
                lambda input: self._prompt_router(input, self.embedding, self.prompt_templates, prompt_embeddings)
            )
            | self.llm
            | StrOutputParser()
        )
        result = chain.invoke(self.input_value)
        return result

from typing import Optional

from langchain.retrievers import MultiQueryRetriever

from langflow.custom import CustomComponent
from langflow.field_typing import BaseRetriever, LanguageModel, PromptTemplate, Text


class MultiQueryRetrieverComponent(CustomComponent):
    display_name = "MultiQueryRetriever"
    description = "Initialize from llm using default template."
    documentation = "https://python.langchain.com/docs/modules/data_connection/retrievers/how_to/MultiQueryRetriever"
    name = "MultiQueryRetriever"

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "prompt": {
                "display_name": "Prompt",
                "default": {
                    "input_variables": ["question"],
                    "input_types": {},
                    "output_parser": None,
                    "partial_variables": {},
                    "template": "You are an AI language model assistant. Your task is \n"
                    "to generate 3 different versions of the given user \n"
                    "question to retrieve relevant documents from a vector database. \n"
                    "By generating multiple perspectives on the user question, \n"
                    "your goal is to help the user overcome some of the limitations \n"
                    "of distance-based similarity search. Provide these alternative \n"
                    "questions separated by newlines. Original question: {question}",
                    "template_format": "f-string",
                    "validate_template": False,
                    "_type": "prompt",
                },
            },
            "retriever": {"display_name": "Retriever"},
            "parser_key": {"display_name": "Parser Key", "default": "lines"},
        }

    def build(
        self,
        llm: LanguageModel,
        retriever: BaseRetriever,
        prompt: Optional[Text] = None,
        parser_key: str = "lines",
    ) -> MultiQueryRetriever:
        if not prompt:
            return MultiQueryRetriever.from_llm(llm=llm, retriever=retriever, parser_key=parser_key)
        else:
            prompt_template = PromptTemplate.from_template(prompt)
            return MultiQueryRetriever.from_llm(
                llm=llm, retriever=retriever, prompt=prompt_template, parser_key=parser_key
            )

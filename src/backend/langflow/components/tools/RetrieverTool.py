from typing import Union

from langchain.schema import BaseRetriever
from langchain.schema.vectorstore import VectorStore
from langchain.tools.retriever import create_retriever_tool

from langflow import CustomComponent
from langflow.field_typing import Tool


class RetrieverToolComponent(CustomComponent):
    display_name = "RetrieverTool"
    description = "Tool for interacting with retriever"

    def build_config(self):
        return {
            "retriever": {"display_name": "Retriever", "info": "Retriever to interact with"},
            "name": {"display_name": "Name", "info": "Name of the tool"},
            "description": {"display_name": "Description", "info": "Description of the tool"},
        }

    def build(
        self,
        retriever: BaseRetriever,
        name: str,
        description: str,
    ) -> Union[Tool]:
        return create_retriever_tool(
            retriever=retriever,
            name=name,
            description=description,
        )

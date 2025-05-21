from langchain_core.tools import create_retriever_tool

from langflow.custom import CustomComponent
from langflow.field_typing import BaseRetriever, Tool


class RetrieverToolComponent(CustomComponent):
    display_name = "RetrieverTool"
    description = "Tool for interacting with retriever"
    name = "RetrieverTool"
    legacy = True
    icon = "LangChain"

    def build_config(self):
        return {
            "retriever": {
                "display_name": "Retriever",
                "info": "Retriever to interact with",
                "type": BaseRetriever,
                "input_types": ["Retriever"],
            },
            "name": {"display_name": "Name", "info": "Name of the tool"},
            "description": {"display_name": "Description", "info": "Description of the tool"},
        }

    def build(self, retriever: BaseRetriever, name: str, description: str, **kwargs) -> Tool:
        _ = kwargs
        return create_retriever_tool(
            retriever=retriever,
            name=name,
            description=description,
        )

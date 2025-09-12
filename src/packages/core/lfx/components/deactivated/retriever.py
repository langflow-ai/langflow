from langchain_core.tools import create_retriever_tool

from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.field_typing import BaseRetriever, Tool
from lfx.io import HandleInput, StrInput


class RetrieverToolComponent(CustomComponent):
    display_name = "RetrieverTool"
    description = "Tool for interacting with retriever"
    name = "RetrieverTool"
    icon = "LangChain"
    legacy = True

    inputs = [
        HandleInput(
            name="retriever",
            display_name="Retriever",
            info="Retriever to interact with",
            input_types=["Retriever"],
            required=True,
        ),
        StrInput(
            name="name",
            display_name="Name",
            info="Name of the tool",
            required=True,
        ),
        StrInput(
            name="description",
            display_name="Description",
            info="Description of the tool",
            required=True,
        ),
    ]

    def build(self, retriever: BaseRetriever, name: str, description: str, **kwargs) -> Tool:
        _ = kwargs
        return create_retriever_tool(
            retriever=retriever,
            name=name,
            description=description,
        )

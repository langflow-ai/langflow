import json
from typing import List

from langchain.base_language import BaseLanguageModel
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.schema import BaseRetriever
from langchain.schema.vectorstore import VectorStore

from langflow.interface.custom.custom_component import CustomComponent


class VectaraSelfQueryRetriverComponent(CustomComponent):
    """
    A custom component for implementing Vectara Self Query Retriever using a vector store.
    """

    display_name: str = "Vectara Self Query Retriever for Vectara Vector Store"
    description: str = "Implementation of Vectara Self Query Retriever"
    documentation = "https://python.langchain.com/docs/integrations/retrievers/self_query/vectara_self_query"
    icon = "Vectara"

    field_config = {
        "code": {"show": True},
        "vectorstore": {"display_name": "Vector Store", "info": "Input Vectara Vectore Store"},
        "llm": {"display_name": "LLM", "info": "For self query retriever"},
        "document_content_description": {
            "display_name": "Document Content Description",
            "info": "For self query retriever",
        },
        "metadata_field_info": {
            "display_name": "Metadata Field Info",
            "info": 'Each metadata field info is a string in the form of key value pair dictionary containing additional search metadata.\nExample input: {"name":"speech","description":"what name of the speech","type":"string or list[string]"}.\nThe keys should remain constant(name, description, type)',
        },
    }

    def build(
        self,
        vectorstore: VectorStore,
        document_content_description: str,
        llm: BaseLanguageModel,
        metadata_field_info: List[str],
    ) -> BaseRetriever:
        metadata_field_obj = []

        for meta in metadata_field_info:
            meta_obj = json.loads(meta)
            if "name" not in meta_obj or "description" not in meta_obj or "type" not in meta_obj:
                raise Exception("Incorrect metadata field info format.")
            attribute_info = AttributeInfo(
                name=meta_obj["name"],
                description=meta_obj["description"],
                type=meta_obj["type"],
            )
            metadata_field_obj.append(attribute_info)

        return SelfQueryRetriever.from_llm(
            llm, vectorstore, document_content_description, metadata_field_obj, verbose=True
        )

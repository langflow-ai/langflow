from typing import Optional, Union, List
from langflow import CustomComponent
import json
import lark
from langchain.vectorstores import Vectara
from langchain.schema import Document
# from langchain.vectorstores.base import VectorStore
from langchain.schema import BaseRetriever
from langchain.embeddings.base import Embeddings
from langchain.schema.vectorstore import VectorStore
from langchain.base_language import BaseLanguageModel
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.embeddings import FakeEmbeddings


class VectaraComponent(CustomComponent):
    display_name: str = "Vectara Self Query Retriever for Vectara Vector Store"
    description: str = "Implementation of Vectara Self Query Retriever"
    documentation = (
        "https://python.langchain.com/docs/integrations/vectorstores/vectara"
    )
    beta = True
    field_config = {
        "code": {"show": False},
        "vectorstore": {
            "display_name": "Vectara Vector Store", 
            "info": "Input Vectara Vectore Store"
            },
        "llm": {
            "display_name": "LLM", 
            "info": "For self query retriever"
            },
        'document_content_description':{
            "display_name": "Document Content Description", 
            "info": "For self query retriever",
            },
        "metadata_field_info": {
            "display_name": "Metadata Field Info", 
            "info": "Check json format in documentation for self query retriever",
            },
    }

    def build(
        self,
        vectorstore: VectorStore = None,
        document_content_description: str = None,
        llm: BaseLanguageModel = None,
        metadata_field_info: List[str] = None,
    ) -> BaseRetriever:
        
        metadata_field_obj = []

        for meta in metadata_field_info:
            meta_obj = json.loads(meta)
            if 'name' not in meta_obj or 'description' not in meta_obj or 'type' not in meta_obj :
                raise Exception('Incorrect metadata field info format.')
            attribute_info = AttributeInfo(
                name = meta_obj['name'],
                description = meta_obj['description'],
                type = meta_obj['type'],
            )
            metadata_field_obj.append(attribute_info)

        return SelfQueryRetriever.from_llm(
            llm,
            vectorstore, 
            document_content_description, 
            metadata_field_obj, 
            verbose=True
        )
    
 
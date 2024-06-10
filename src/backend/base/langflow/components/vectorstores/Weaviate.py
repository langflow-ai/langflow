from typing import Optional, Union

import weaviate  # type: ignore
from langchain_community.vectorstores import Weaviate
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore

from langflow.custom import CustomComponent
from langflow.schema import Record


class WeaviateVectorStoreComponent(CustomComponent):
    display_name: str = "Weaviate"
    description: str = "Implementation of Vector Store using Weaviate"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/weaviate"
    field_config = {
        "url": {"display_name": "Weaviate URL", "value": "http://localhost:8080"},
        "api_key": {
            "display_name": "API Key",
            "password": True,
            "required": False,
        },
        "index_name": {
            "display_name": "Index name",
            "required": False,
        },
        "text_key": {
            "display_name": "Text Key",
            "required": False,
            "advanced": True,
            "value": "text",
        },
        "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
        "embedding": {"display_name": "Embedding"},
        "attributes": {
            "display_name": "Attributes",
            "required": False,
            "is_list": True,
            "field_type": "str",
            "advanced": True,
        },
        "search_by_text": {
            "display_name": "Search By Text",
            "field_type": "bool",
            "advanced": True,
        },
        "code": {"show": False},
    }

    def build(
        self,
        url: str,
        index_name: str,
        search_by_text: bool = False,
        api_key: Optional[str] = None,
        text_key: str = "text",
        embedding: Optional[Embeddings] = None,
        inputs: Optional[Record] = None,
        attributes: Optional[list] = None,
    ) -> Union[VectorStore, BaseRetriever]:
        if api_key:
            auth_config = weaviate.AuthApiKey(api_key=api_key)
            client = weaviate.Client(url=url, auth_client_secret=auth_config)
        else:
            client = weaviate.Client(url=url)

        def _to_pascal_case(word: str):
            if word and not word[0].isupper():
                word = word.capitalize()

            if word.isidentifier():
                return word

            word = word.replace("-", " ").replace("_", " ")
            parts = word.split()
            pascal_case_word = "".join([part.capitalize() for part in parts])

            return pascal_case_word

        index_name = _to_pascal_case(index_name) if index_name else None
        if not index_name:
            raise ValueError("Index name is required")
        documents: list[Document] = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            elif isinstance(_input, Document):
                documents.append(_input)

        if documents and embedding is not None:
            return Weaviate.from_documents(
                client=client,
                index_name=index_name,
                documents=documents,
                embedding=embedding,
                by_text=search_by_text,
            )

        return Weaviate(
            client=client,
            index_name=index_name,
            text_key=text_key,
            embedding=embedding,
            by_text=search_by_text,
            attributes=attributes if attributes is not None else [],
        )

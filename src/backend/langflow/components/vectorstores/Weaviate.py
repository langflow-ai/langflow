import weaviate  # type: ignore
from typing import Optional, Union
from langflow import CustomComponent

from langchain.vectorstores import Weaviate
from langchain.schema import Document
from langchain.vectorstores.base import VectorStore
from langchain.schema import BaseRetriever
from langchain.embeddings.base import Embeddings


class WeaviateVectorStore(CustomComponent):
    display_name: str = "Weaviate"
    description: str = "Implementation of Vector Store using Weaviate"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/weaviate"
    beta = True
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
        "text_key": {"display_name": "Text Key", "required": False, "advanced": True, "value": "text"},
        "documents": {"display_name": "Documents", "is_list": True},
        "embedding": {"display_name": "Embedding"},
        "attributes": {
            "display_name": "Attributes",
            "required": False,
            "is_list": True,
            "field_type": "str",
            "advanced": True,
        },
        "search_by_text": {"display_name": "Search By Text", "field_type": "bool", "advanced": True},
        "code": {"show": False},
    }

    def build(
        self,
        url: str,
        search_by_text: bool = False,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
        text_key: Optional[str] = "text",
        embedding: Optional[Embeddings] = None,
        documents: Optional[Document] = None,
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

        if documents is not None and embedding is not None:
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

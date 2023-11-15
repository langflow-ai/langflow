from typing import Optional, Union

from langchain.schema import BaseRetriever, Document
from langchain.vectorstores import Vectara
from langchain.vectorstores.base import VectorStore

from langflow import CustomComponent


class VectaraComponent(CustomComponent):
    display_name: str = "Vectara"
    description: str = "Implementation of Vector Store using Vectara"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/vectara"
    beta = True
    # api key should be password = True
    field_config = {
        "vectara_customer_id": {"display_name": "Vectara Customer ID"},
        "vectara_corpus_id": {"display_name": "Vectara Corpus ID"},
        "vectara_api_key": {"display_name": "Vectara API Key", "password": True},
        "code": {"show": False},
        "documents": {"display_name": "Documents"},
    }

    def build(
        self,
        vectara_customer_id: str,
        vectara_corpus_id: str,
        vectara_api_key: str,
        documents: Optional[Document] = None,
    ) -> Union[VectorStore, BaseRetriever]:
        # If documents, then we need to create a Vectara instance using .from_documents
        if documents is not None:
            return Vectara.from_documents(
                documents=documents,  # type: ignore
                vectara_customer_id=vectara_customer_id,
                vectara_corpus_id=vectara_corpus_id,
                vectara_api_key=vectara_api_key,
                source="langflow",
            )

        return Vectara(
            vectara_customer_id=vectara_customer_id,
            vectara_corpus_id=vectara_corpus_id,
            vectara_api_key=vectara_api_key,
            source="langflow",
        )

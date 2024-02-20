import tempfile
import urllib
import urllib.request
from typing import List, Optional, Union

from langchain_community.embeddings import FakeEmbeddings
from langchain_community.vectorstores.vectara import Vectara
from langchain_core.vectorstores import VectorStore
from langflow import CustomComponent
from langflow.field_typing import BaseRetriever, Document


class VectaraComponent(CustomComponent):
    display_name: str = "Vectara"
    description: str = "Implementation of Vector Store using Vectara"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/vectara"
    beta = True
    field_config = {
        "vectara_customer_id": {
            "display_name": "Vectara Customer ID",
        },
        "vectara_corpus_id": {
            "display_name": "Vectara Corpus ID",
        },
        "vectara_api_key": {
            "display_name": "Vectara API Key",
            "password": True,
        },
        "documents": {"display_name": "Documents", "info": "If provided, will be upserted to corpus (optional)"},
        "files_url": {
            "display_name": "Files Url",
            "info": "Make vectara object using url of files (optional)",
        },
    }

    def build(
        self,
        vectara_customer_id: str,
        vectara_corpus_id: str,
        vectara_api_key: str,
        files_url: Optional[List[str]] = None,
        documents: Optional[Document] = None,
    ) -> Union[VectorStore, BaseRetriever]:
        source = "Langflow"

        if documents is not None:
            return Vectara.from_documents(
                documents=documents,  # type: ignore
                embedding=FakeEmbeddings(size=768),
                vectara_customer_id=vectara_customer_id,
                vectara_corpus_id=vectara_corpus_id,
                vectara_api_key=vectara_api_key,
                source=source,
            )

        if files_url is not None:
            files_list = []
            for url in files_url:
                name = tempfile.NamedTemporaryFile().name
                urllib.request.urlretrieve(url, name)
                files_list.append(name)

            return Vectara.from_files(
                files=files_list,
                embedding=FakeEmbeddings(size=768),
                vectara_customer_id=vectara_customer_id,
                vectara_corpus_id=vectara_corpus_id,
                vectara_api_key=vectara_api_key,
                source=source,
            )

        return Vectara(
            vectara_customer_id=vectara_customer_id,
            vectara_corpus_id=vectara_corpus_id,
            vectara_api_key=vectara_api_key,
            source=source,
        )

from langchain.embeddings.base import Embeddings
from langchain_community.vectorstores import Qdrant
import os

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from typing import Dict
from langflow.helpers.data import docs_to_data
from langflow.inputs.inputs import MessageTextInput
from langflow.io import (
    DropdownInput,
    HandleInput,
    IntInput,
    SecretStrInput,
    StrInput,
    BoolInput
)
from langflow.schema.data import Data
import uuid


class QdrantVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Qdrant"
    description = "Qdrant Vector Store with search capabilities"
    icon = "Qdrant"

    inputs = [
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        MessageTextInput(name="document_uuid", display_name="Document UUID", required=False,tool_mode=True),
        StrInput(name="host", display_name="Host", value="localhost", advanced=True),
        IntInput(name="port", display_name="Port", value=6333, advanced=True),
        IntInput(name="grpc_port", display_name="gRPC Port", value=6334, advanced=True),
        SecretStrInput(name="api_key", display_name="Qdrant API Key", required=False),
        StrInput(name="prefix", display_name="Prefix", advanced=True),
        IntInput(name="timeout", display_name="Timeout", advanced=True),
        StrInput(name="path", display_name="Path", advanced=True),
        StrInput(name="url", display_name="URL", advanced=True),
        DropdownInput(
            name="distance_func",
            display_name="Distance Function",
            options=["Cosine", "Euclidean", "Dot Product"],
            value="Cosine",
            advanced=True,
        ),
        StrInput(name="content_payload_key", display_name="Content Payload Key", value="page_content", advanced=True),
        StrInput(name="metadata_payload_key", display_name="Metadata Payload Key", value="metadata", advanced=True),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
        BoolInput(
            name="return_doc_uuids",
            display_name="Return Document UUIDs",
            value=True,
            advanced=True,
            info="will return list of unique document ids",
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> Qdrant:
        qdrant_kwargs = {
            "collection_name": self.collection_name,
            "content_payload_key": self.content_payload_key,
            "metadata_payload_key": self.metadata_payload_key,
        }

        api_key = self.api_key or os.getenv("QUADRANT_API_KEY", "")

        server_kwargs = {
            "host": self.host or None,
            "port": int(self.port),  # Ensure port is an integer
            "grpc_port": int(self.grpc_port),  # Ensure grpc_port is an integer
            "api_key": api_key,
            "prefix": self.prefix,
            # Ensure timeout is an integer
            "timeout": int(self.timeout) if self.timeout else None,
            "path": self.path or None,
            "url": self.url or None,
        }

        server_kwargs = {k: v for k, v in server_kwargs.items() if v is not None}

        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            # document_uuid = str(uuid.uuid4())

            if isinstance(_input, Data):
                if _input.model_dump().get('data',{}).get('result',[]):
                    for page in _input.model_dump().get('data',{}).get('result',[]):
                        # page['document_uuid'] =document_uuid
                        page = Data(data=page)
                        documents.append(page.to_lc_document())
                else:
                    # _input.document_uuid = document_uuid
                    documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if not isinstance(self.embedding, Embeddings):
            msg = "Invalid embedding object"
            raise TypeError(msg)

        if documents:
            qdrant = Qdrant.from_documents(documents, embedding=self.embedding, **qdrant_kwargs, **server_kwargs)
        else:
            from qdrant_client import QdrantClient

            client = QdrantClient(**server_kwargs)
            qdrant = Qdrant(embeddings=self.embedding, client=client, **qdrant_kwargs)

        return qdrant

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()
        base_filter: Dict = {"document_uuid": self.document_uuid}
        print(f'base filter {base_filter}')
        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
                filter = base_filter
            )
            data = docs_to_data(docs)
            # logger.warning(f'from qdrant db : {data[0].model_dump()['data']}')
            self.status = data
            if self.return_doc_uuids:
                
                new_data=[]
                for page in data:
                    x=page.model_dump()['data']
                    x = x['document_uuid']
                    page=Data(text=x)
                    new_data.append(page)
                return new_data
                # x= data[0].model_dump()['data']
                # logger.warning(f'qdrant logs : {(x['document_uuid'])}')
                # data = [item['document_uuid'] for item in x]
                # data =x['document_uuid']
            return data
        return []

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
    BoolInput,
    DictInput
)
from langflow.schema.data import Data
import uuid
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

class QdrantVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Qdrant"
    description = "Qdrant Vector Store with search capabilities"
    icon = "Qdrant"

    inputs = [
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        MessageTextInput(name="document_hash", display_name="Document Hash", required=False, tool_mode=True),
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
        DictInput(    
            name="filters",
            display_name="Filters ",
            info=(
                "Filters on Metadata"
            ),
            input_types=["Data"],
            show=True,
            required=False,
            is_list=True,
            tool_mode=True
        )
    ]

    def _check_document_exists(self, client: QdrantClient, document_hash: str) -> bool:
        """Check if a document with the given hash already exists in the collection."""
        if not document_hash:
            return False
            
        try:
            # Check if collection exists first
            collections = client.get_collections().collections
            collection_exists = any(col.name == self.collection_name for col in collections)
            
            if not collection_exists:
                logger.info(f"Collection {self.collection_name} does not exist yet")
                return False
            
            # Search for documents with matching hash
            search_result = client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="metadata.file_hash",
                            match=MatchValue(value=document_hash)
                        )
                    ]
                ),
                limit=1
            )
            
            # If we found any points, the document exists
            points, _ = search_result
            exists = len(points) > 0
            
            if exists:
                logger.info(f"Document with hash {document_hash} already exists in collection {self.collection_name}")
            else:
                logger.info(f"Document with hash {document_hash} not found, will proceed with ingestion")
            
            return exists
            
        except Exception as e:
            logger.error(f"Error checking document existence: {e}")
            return False

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
            "port": int(self.port),
            "grpc_port": int(self.grpc_port),
            "api_key": api_key,
            "prefix": self.prefix,
            "timeout": int(self.timeout) if self.timeout else None,
            "path": self.path or None,
            "url": self.url or None,
        }

        server_kwargs = {k: v for k, v in server_kwargs.items() if v is not None}

        # Create Qdrant client
        client = QdrantClient(**server_kwargs)

        # Check if document already exists before processing
        logger.warning(f"ingestion - document with hash {self.document_hash} checking")
        if self.document_hash:
            if self._check_document_exists(client, self.document_hash):
                logger.info(f"Skipping ingestion - document with hash {self.document_hash} already exists")
                # Return existing vector store without ingesting
                return Qdrant(embeddings=self.embedding, client=client, **qdrant_kwargs)

        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                if _input.model_dump().get('data', {}).get('result', []):
                    for page in _input.model_dump().get('data', {}).get('result', []):
                        page_data = Data(data=page)
                        doc = page_data.to_lc_document()
                        
                        # Add hash to metadata if provided
                        if self.document_hash:
                            if not hasattr(doc, 'metadata') or doc.metadata is None:
                                doc.metadata = {}
                            doc.metadata['file_hash'] = self.document_hash
                        
                        documents.append(doc)
                else:
                    doc = _input.to_lc_document()
                    
                    # Add hash to metadata if provided
                    if self.document_hash:
                        if not hasattr(doc, 'metadata') or doc.metadata is None:
                            doc.metadata = {}
                        doc.metadata['file_hash'] = self.document_hash
                    
                    documents.append(doc)
            else:
                # Add hash to metadata if provided
                if self.document_hash:
                    if not hasattr(_input, 'metadata') or _input.metadata is None:
                        _input.metadata = {}
                    _input.metadata['file_hash'] = self.document_hash
                
                documents.append(_input)

        if not isinstance(self.embedding, Embeddings):
            msg = "Invalid embedding object"
            raise TypeError(msg)

        if documents:
            logger.info(f"Ingesting {len(documents)} documents with hash {self.document_hash}")
            qdrant = Qdrant.from_documents(documents, embedding=self.embedding, **qdrant_kwargs, **server_kwargs)
        else:
            qdrant = Qdrant(embeddings=self.embedding, client=client, **qdrant_kwargs)

        return qdrant

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()
        cleaned_filters = {} if not self.filters else self.filters 
        if self.document_hash:
            cleaned_filters["file_hash"] = self.document_hash
        cleaned_filters = {k: v for k, v in self.filters.items() if k != "" and v != ""}
        logger.warning(f'base filter {cleaned_filters}')
        
        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
                filter=cleaned_filters
            )
            data = docs_to_data(docs)
            self.status = data
            return data
        return []
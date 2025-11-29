from langchain.embeddings.base import Embeddings
from langchain_community.vectorstores import Qdrant
import os
import json

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from typing import Any, Dict, List
from langflow.helpers.data import docs_to_data
from langflow.inputs.inputs import MessageTextInput
from langflow.io import (
    DropdownInput,
    HandleInput,
    IntInput,
    SecretStrInput,
    StrInput,
    BoolInput,
    DictInput,
    Output,
)
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
import pandas as pd
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue


class QdrantVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Qdrant"
    description = "Qdrant Vector Store with search capabilities"
    icon = "Qdrant"

    # holds the last ingestion summary as JSON string
    last_ingestion_json: str | None = None

    inputs = [
        StrInput(name="collection_name", display_name="Collection Name", required=True, real_time_refresh=True),
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
            info="Filters on Metadata",
            input_types=["Data"],
            show=True,
            required=False,
            is_list=False,  # expect a single dict
            tool_mode=True
        ),
        BoolInput(
            name="return_text_only",
            display_name="Return Text Only",
            info="If true, returns only the text column from search results as a DataFrame.",
            value=False,
            advanced=True,
        )
    ]

    outputs = [
        Output(
            display_name="Search Results",
            name="search_results",
            method="search_documents",
        ),
        Output(
            display_name="Ingestion Result",
            name="ingestion_result",
            method="get_ingestion_result",
        ),
    ]

    def _check_document_exists(self, client: QdrantClient, document_hash: str) -> bool:
        """Check if a document with the given hash already exists in the collection."""
        if not document_hash:
            return False

        try:
            collections = client.get_collections().collections
            collection_exists = any(col.name == self.collection_name for col in collections)

            if not collection_exists:
                logger.info(f"Collection {self.collection_name} does not exist yet")
                return False

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

    def update_build_config(self, build_config, field_value, field_name=None):
        """Update build config when collection_name changes to set API key default."""
        if field_name == "collection_name":
            # Set API key default from environment variable
            build_config["host"]["value"] = os.environ.get("QUADRANT_HOST", "")
            build_config["port"]["value"] = os.environ.get("QUADRANT_PORT", "")
            build_config["grpc_port"]["value"] = os.environ.get("QUADRANT_GRPC_PORT", "")
            build_config["api_key"]["value"] = os.environ.get("QUADRANT_API_KEY", "")
        return build_config

    @check_cached_vector_store
    def build_vector_store(self) -> Qdrant:
        qdrant_kwargs = {
            "collection_name": self.collection_name,
            "content_payload_key": self.content_payload_key,
            "metadata_payload_key": self.metadata_payload_key,
        }

        # Try both common env var spellings
        api_key = self.api_key or os.environ.get("QDRANT_API_KEY", "") or os.environ.get("QUADRANT_API_KEY", "")

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

        # if doc already ingested, skip and return store; also set JSON result
        logger.warning(f"ingestion - document with hash {self.document_hash} checking")
        if self.document_hash:
            if self._check_document_exists(client, self.document_hash):
                logger.info(f"Skipping ingestion - document with hash {self.document_hash} already exists")
                result_data = {
                    "status": "skipped",
                    "reason": "document_exists",
                    "file_hash": self.document_hash,
                    "pages": []
                }
                self.last_ingestion_json = json.dumps(result_data, indent=2)
                return Qdrant(embeddings=self.embedding, client=client, **qdrant_kwargs)

        # Prepare ingest inputs from parents
        self.ingest_data = self._prepare_ingest_data()

        documents: List[Any] = []
        page_info: List[Dict[str, Any]] = []
        extracted_file_hash: str | None = None

        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                # Extract file_hash from the Data object
                if not extracted_file_hash:
                    extracted_file_hash = _input.model_dump().get('data', {}).get('file_hash')
                
                result_pages = _input.model_dump().get('data', {}).get('result', [])
                
                # Fallback: try to extract file_hash from first page in result_pages
                if not extracted_file_hash and result_pages and len(result_pages) > 0:
                    extracted_file_hash = result_pages[0].get('file_hash')
                if result_pages:
                    for page in result_pages:
                        page_data = Data(data=page)
                        doc = page_data.to_lc_document()

                        # ensure metadata dict
                        if not hasattr(doc, 'metadata') or doc.metadata is None:
                            doc.metadata = {}

                        # attach file hash (prefer extracted, fallback to document_hash)
                        file_hash_to_use = extracted_file_hash or self.document_hash
                        if file_hash_to_use:
                            doc.metadata['file_hash'] = file_hash_to_use

                        documents.append(doc)

                        # collect page info (no status here, just page details)
                        page_info.append({
                            "page_number": doc.metadata.get("page_number"),
                            "content_len": len(getattr(doc, "page_content", "") or ""),
                        })
                else:
                    doc = _input.to_lc_document()
                    if not hasattr(doc, 'metadata') or doc.metadata is None:
                        doc.metadata = {}
                    file_hash_to_use = extracted_file_hash or self.document_hash
                    if file_hash_to_use:
                        doc.metadata['file_hash'] = file_hash_to_use
                    documents.append(doc)
                    page_info.append({
                        "page_number": doc.metadata.get("page_number"),
                        "content_len": len(getattr(doc, "page_content", "") or ""),
                    })
            else:
                # Assume already an LC document-like
                if not hasattr(_input, 'metadata') or _input.metadata is None:
                    _input.metadata = {}
                file_hash_to_use = extracted_file_hash or self.document_hash
                if file_hash_to_use:
                    _input.metadata['file_hash'] = file_hash_to_use
                documents.append(_input)
                page_info.append({
                    "page_number": getattr(_input, "metadata", {}).get("page_number"),
                    "content_len": len(getattr(_input, "page_content", "") or ""),
                })

        if not isinstance(self.embedding, Embeddings):
            raise TypeError("Invalid embedding object")

        # Use extracted file hash if available, otherwise fall back to document_hash
        final_file_hash = extracted_file_hash or self.document_hash

        if documents:
            # INGESTS into Qdrant
            qdrant = Qdrant.from_documents(
                documents,
                embedding=self.embedding,
                **qdrant_kwargs,
                **server_kwargs
            )

            # Build result with status at outer level
            result_data = {
                "status": "ingested",
                "file_hash": final_file_hash,
                "pages": page_info
            }
            
            # Store as JSON string
            self.last_ingestion_json = json.dumps(result_data, indent=2)
        else:
            # no docs prepared
            qdrant = Qdrant(embeddings=self.embedding, client=client, **qdrant_kwargs)
            result_data = {
                "status": "no_input",
                "reason": "no_documents_prepared",
                "file_hash": final_file_hash,
                "pages": []
            }
            self.last_ingestion_json = json.dumps(result_data, indent=2)

        return qdrant

    def get_ingestion_result(self) -> Message:
        """
        Output #2: return a JSON string with the last ingestion summary.
        """
        if self.last_ingestion_json is None:
            # Force a build to populate result if not already run
            _ = self.build_vector_store()
        return self.last_ingestion_json if self.last_ingestion_json is not None else json.dumps({"status": "no_data", "file_hash": None, "pages": []}, indent=2)

    def search_documents(self) -> List[Data] | DataFrame:
        """
        Output #1: standard similarity search results as Data objects, or DataFrame with text column only if return_text_only is True.
        """
        vector_store = self.build_vector_store()

        # Normalize filters to a dict
        base_filters = self.filters if isinstance(self.filters, dict) else {}
        base_filters = {k: v for k, v in base_filters.items() if k not in (None, "",) and v not in (None, "", [])}

        # Inject file_hash constraint if provided
        if self.document_hash:
            base_filters["file_hash"] = self.document_hash

        logger.warning(f'base filter {base_filters}')

        if self.document_hash or base_filters or (self.search_query and isinstance(self.search_query, str) and self.search_query.strip()):
            docs = vector_store.similarity_search(
                query=self.search_query or "",
                k=int(self.number_of_results),
                filter=base_filters or None
            )
            
            # If return_text_only is True, convert to DataFrame with text column only
            if self.return_text_only:
                data = docs_to_data(docs)
                # Convert Data list to DataFrame
                df_data = [item.data for item in data]
                df = pd.DataFrame(df_data)
                
                # Return only the text column if it exists
                if 'text' in df.columns:
                    return DataFrame(df[['text']])
                else:
                    # Fallback: return empty DataFrame with text column
                    return DataFrame(pd.DataFrame({'text': []}))
            
            # Default behavior: return Data objects
            data = docs_to_data(docs)
            return data
        
        # Return empty result based on return_text_only flag
        if self.return_text_only:
            return DataFrame(pd.DataFrame({'text': []}))
        return []
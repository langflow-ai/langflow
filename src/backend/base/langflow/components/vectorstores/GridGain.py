from typing import TYPE_CHECKING, Optional, List, Union
import pandas as pd
from loguru import logger
from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import HandleInput, IntInput, MessageTextInput, StrInput, FileInput, FloatInput
from langflow.schema import Data
from langchain.schema import Document
from pygridgain import Client
from langchain_gridgain.vectorstores import GridGainVectorStore

class GridGainVectorStoreComponent(LCVectorStoreComponent):
    """GridGain Vector Store with enhanced CSV handling capabilities."""

    display_name: str = "GridGain"
    description: str = "GridGain Vector Store with CSV ingestion and search capabilities"
    documentation = "https://www.gridgain.com/docs/latest/index"
    name = "GridGain"
    icon = "GridGain"

    inputs = [
        StrInput(name="cache_name", display_name="Cache Name", required=True),
        StrInput(name="host", display_name="Host", required=True),
        IntInput(name="port", display_name="Port", required=True),
        FloatInput(name="score_threshold", display_name="score_threshold ", required=True, value=0.6),
        FileInput(
            name="csv_file",
            display_name="CSV File",
            file_types=["csv"],
            required=False,
        ),
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"],
        ),
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
        ),
    ]

    def process_csv(self, csv_path: str) -> List[Document]:
        """Process CSV file and convert to list of document objects."""
        try:
            df = pd.read_csv(csv_path)
            documents = []
            
            for _, row in df.iterrows():
                title = row.get('title', '')
                text = row.get('text', '')
                
                content = f"{title}\n{text}".strip()
                
                metadata = {
                    "id": str(row.get('id', '')),
                    "url": row.get('url', ''),
                    "vector_id": row.get('vector_id', '')
                }
                
                if content:
                    documents.append(
                        Document(
                            page_content=content,
                            metadata=metadata
                        )
                    )
            
            logger.info(f"Processed {len(documents)} documents from CSV")
            return documents
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            raise

    @check_cached_vector_store
    def build_vector_store(self) -> "GridGainVectorStore":
        """Builds the GridGain Vector Store object with CSV support."""
        try:
            # Connect to GridGain using provided host and port
            client = self.connect_to_gridgain(self.host, self.port)
            logger.info(f"Connected to GridGain at {self.host}:{self.port}")

            gridgain = GridGainVectorStore(
                cache_name=self.cache_name,
                embedding=self.embedding,
                client=client
            )

            # Process CSV if provided
            if hasattr(self, 'csv_file') and self.csv_file:
                documents = self.process_csv(self.csv_file)
                if documents:
                    logger.info(f"Adding {len(documents)} documents from CSV to GridGain")
                    gridgain.add_documents(documents)
                    self.status = f"Added {len(documents)} documents from CSV to GridGain"

            return gridgain

        except Exception as e:
            logger.error(f"Error during GridGain Vector Store initialization: {e}")
            self.status = f"Error: {str(e)}"
            raise
    
    def connect_to_gridgain(self, host: str, port: int) -> Client:
        """Connect to GridGain server using provided host and port."""
        try:
            client = Client()
            client.connect(host, port)
            logger.info(f"Connected to GridGain server at {host}:{port} successfully.")
            return client
        except Exception as e:
            logger.exception(f"Failed to connect to GridGain: {e}")
            raise

    def search_documents(self) -> list[Data]:
        """Search documents with enhanced error handling."""
        try:
            vector_store = self.build_vector_store()

            if not self.search_query or not isinstance(self.search_query, str) or not self.search_query.strip():
                self.status = "No search query provided"
                return []

            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
                score_threshold=self.score_threshold
            )

            data = docs_to_data(docs)
            self.status = f"Found {len(data)} results for the query: {self.search_query}"
            return data
            
        except Exception as e:
            logger.error(f"Error during search: {e}")
            self.status = f"Search error: {str(e)}"
            return []

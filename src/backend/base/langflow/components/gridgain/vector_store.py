import uuid

from langchain.schema import Document
from langchain_gridgain.vectorstores import GridGainVectorStore
from loguru import logger
from pygridgain import Client

from langflow.base.vectorstores.model import (
    LCVectorStoreComponent,
    check_cached_vector_store,
)
from langflow.helpers import docs_to_data
from langflow.inputs import FloatInput
from langflow.io import (
    HandleInput,
    IntInput,
    MessageTextInput,
    StrInput,
)
from langflow.schema import Data


class GridGainVectorStoreComponent(LCVectorStoreComponent):
    display_name: str = "GridGain"
    description: str = "GridGain Vector Store with search capabilities"
    documentation: str = "https://www.gridgain.com/docs/latest/index"
    name = "GridGain"
    icon = "GridGain"

    inputs = [
        StrInput(
            name="cache_name",
            display_name="Cache Name",
            info="Name of the GridGain cache where vectors will be stored. Cache Will be created if it doesn't exist.",
            required=True,
        ),
        StrInput(name="host", display_name="Host", info="GridGain server hostname or IP address", required=True),
        IntInput(
            name="port",
            display_name="Port",
            info="GridGain server port number (default: 10800)",
            required=True,
            value=10800,
        ),
        FloatInput(
            name="score_threshold",
            display_name="Score Threshold",
            info="Minimum similarity score (0-1) [default: 0.6]",
            required=True,
            value=0.6,
        ),
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"],
            required=True,
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
        *LCVectorStoreComponent.inputs,
    ]

    def _process_data_input(self, data_input: Data) -> Document:
        """Process a single Data input into a Document.

        Args:
            data_input (Data): Input data object to process

        Returns:
            Document: Processed LangChain Document with validated metadata

        Raises:
            TypeError: If input is not a valid Data object
            ValueError: If required metadata fields are missing or invalid
        """
        try:
            # Convert Data to LangChain Document
            doc = data_input.to_lc_document()

            # Ensure document has metadata
            if not hasattr(doc, "metadata") or doc.metadata is None:
                doc.metadata = {}

            # Ensure required metadata fields with proper formatting
            doc_id = str(doc.metadata.get("id", uuid.uuid4()))
            doc.metadata.update(
                {
                    "id": doc_id,
                    "vector_id": str(doc.metadata.get("vector_id", doc_id)),
                    "url": str(doc.metadata.get("url", "")),
                    "title": str(doc.metadata.get("title", "")),
                }
            )
        except Exception as e:
            logger.error(f"Error processing data input: {e}")
            raise

        return doc

    def _add_documents_to_vector_store(self, vector_store: GridGainVectorStore) -> None:
        """Add documents from ingest_data to the vector store using add_texts."""
        try:
            documents = []
            texts = []
            metadatas = []

            for _input in self.ingest_data or []:
                if isinstance(_input, Data):
                    doc = self._process_data_input(_input)
                    documents.append(doc)
                    texts.append(doc.page_content)
                    metadatas.append(doc.metadata)
                else:
                    msg = "Vector Store Inputs must be Data objects."
                    raise TypeError(msg)

            if documents:
                logger.info(f"Adding {len(documents)} documents to the Vector Store")
                vector_store.add_texts(texts=texts, metadatas=metadatas)
                self.log(f"Successfully added {len(documents)} documents to GridGain")
            else:
                logger.info("No documents to add to the Vector Store")

        except Exception as e:
            msg = f"Error adding documents to GridGainVectorStore: {e}"
            logger.error(msg)
            raise ValueError(msg) from e

    @check_cached_vector_store
    def build_vector_store(self) -> GridGainVectorStore:
        """Build and return a configured GridGain vector store.

        Returns:
            vector_store: A configured instance of the GridGain vector store

        Raises:
            ImportError: If failed to import langchain Gridgain integration package.
            ValueError: If connection to GridGain fails or If vector store initialization fails.
        """
        try:
            # Connect to GridGain
            client = Client()
            client.connect(self.host, self.port)
            logger.info(f"Connected to GridGain at {self.host}:{self.port}")

            # Initialize vector store
            vector_store = GridGainVectorStore(cache_name=self.cache_name, embedding=self.embedding, client=client)

            # Add documents from ingest_data
            self._add_documents_to_vector_store(vector_store)
        except Exception as e:
            logger.error(f"Error building vector store: {e}")
            raise
        return vector_store

    def search_documents(self, vector_store=None) -> list[Data]:
        """Search documents using similarity search in the vector store.

        Args:
            vector_store (Optional[GridGainVectorStore]): An existing vector store instance.
            If None, a new instance will be created.

        Returns:
            list[Data]: List of matching documents as Data objects

        Raises:
            ValueError: If search query is invalid or empty
        """
        try:
            vector_store = vector_store or self.build_vector_store()

            if not self.search_query or not isinstance(self.search_query, str) or not self.search_query.strip():
                self.log("No search query provided")
                return []

            docs = vector_store.similarity_search(
                query=self.search_query, k=self.number_of_results, score_threshold=self.score_threshold
            )

            data = docs_to_data(docs)
            self.log(f"Found {len(data)} results for the query: {self.search_query}")

        except Exception as e:
            logger.error(f"Error during search: {e}")
            raise
        return data

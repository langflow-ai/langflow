import numpy as np
from langchain_pinecone import Pinecone

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import DropdownInput, HandleInput, IntInput, SecretStrInput, StrInput
from langflow.schema import Data


class PineconeVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Pinecone"
    description = "Pinecone Vector Store with search capabilities"
    name = "Pinecone"
    icon = "Pinecone"
    inputs = [
        StrInput(name="index_name", display_name="Index Name", required=True),
        StrInput(name="namespace", display_name="Namespace", info="Namespace for the index."),
        DropdownInput(
            name="distance_strategy",
            display_name="Distance Strategy",
            options=["Cosine", "Euclidean", "Dot Product"],
            value="Cosine",
            advanced=True,
        ),
        SecretStrInput(name="pinecone_api_key", display_name="Pinecone API Key", required=True),
        StrInput(
            name="text_key",
            display_name="Text Key",
            info="Key in the record to use as text.",
            value="text",
            advanced=True,
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> Pinecone:
        """Build and return a Pinecone vector store instance."""
        try:
            from langchain_pinecone._utilities import DistanceStrategy

            # Wrap the embedding model to ensure float32 output
            wrapped_embeddings = Float32Embeddings(self.embedding)

            # Convert distance strategy
            distance_strategy = self.distance_strategy.replace(" ", "_").upper()
            distance_strategy = DistanceStrategy[distance_strategy]

            # Initialize Pinecone instance with wrapped embeddings
            pinecone = Pinecone(
                index_name=self.index_name,
                embedding=wrapped_embeddings,  # Use wrapped embeddings
                text_key=self.text_key,
                namespace=self.namespace,
                distance_strategy=distance_strategy,
                pinecone_api_key=self.pinecone_api_key,
            )
        except Exception as e:
            error_msg = "Error building Pinecone vector store"
            raise ValueError(error_msg) from e
        else:
            # Process documents if any
            documents = []
            if self.ingest_data:
                for doc in self.ingest_data:
                    if isinstance(doc, Data):
                        documents.append(doc.to_lc_document())
                    else:
                        documents.append(doc)

                if documents:
                    pinecone.add_documents(documents)

            return pinecone

    def search_documents(self) -> list[Data]:
        """Search documents in the vector store."""
        try:
            if not self.search_query or not isinstance(self.search_query, str) or not self.search_query.strip():
                return []

            vector_store = self.build_vector_store()
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )
        except Exception as e:
            error_msg = "Error searching documents"
            raise ValueError(error_msg) from e
        else:
            data = docs_to_data(docs)
            self.status = data
            return data


class Float32Embeddings:
    """Wrapper class to ensure float32 embeddings."""

    def __init__(self, base_embeddings):
        self.base_embeddings = base_embeddings

    def embed_documents(self, texts):
        embeddings = self.base_embeddings.embed_documents(texts)
        if isinstance(embeddings, np.ndarray):
            return [[self._force_float32(x) for x in vec] for vec in embeddings]
        return [[self._force_float32(x) for x in vec] for vec in embeddings]

    def embed_query(self, text):
        embedding = self.base_embeddings.embed_query(text)
        if isinstance(embedding, np.ndarray):
            return [self._force_float32(x) for x in embedding]
        return [self._force_float32(x) for x in embedding]

    def _force_float32(self, value):
        """Convert any numeric type to Python float."""
        return float(np.float32(value))

from langchain_community.vectorstores import FAISS

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, HandleInput, IntInput, StrInput
from langflow.schema import Data


class FaissVectorStoreComponent(LCVectorStoreComponent):
    """FAISS Vector Store with search capabilities."""

    display_name: str = "FAISS"
    description: str = "FAISS Vector Store with search capabilities"
    name = "FAISS"
    icon = "FAISS"

    inputs = [
        StrInput(
            name="index_name",
            display_name="Index Name",
            value="langflow_index",
        ),
        StrInput(
            name="persist_directory",
            display_name="Persist Directory",
            info="Path to save the FAISS index. It will be relative to where Langflow is running.",
        ),
        *LCVectorStoreComponent.inputs,
        BoolInput(
            name="allow_dangerous_deserialization",
            display_name="Allow Dangerous Deserialization",
            info="Set to True to allow loading pickle files from untrusted sources. "
            "Only enable this if you trust the source of the data.",
            advanced=True,
            value=True,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=4,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> FAISS:
        """Builds the FAISS object."""
        if not self.persist_directory:
            msg = "Folder path is required to save the FAISS index."
            raise ValueError(msg)
        path = self.resolve_path(self.persist_directory)

        documents = []

        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        faiss = FAISS.from_documents(documents=documents, embedding=self.embedding)
        faiss.save_local(str(path), self.index_name)

        return faiss

    def search_documents(self) -> list[Data]:
        """Search for documents in the FAISS vector store."""
        if not self.persist_directory:
            msg = "Folder path is required to load the FAISS index."
            raise ValueError(msg)
        path = self.resolve_path(self.persist_directory)

        vector_store = FAISS.load_local(
            folder_path=path,
            embeddings=self.embedding,
            index_name=self.index_name,
            allow_dangerous_deserialization=self.allow_dangerous_deserialization,
        )

        if not vector_store:
            msg = "Failed to load the FAISS index."
            raise ValueError(msg)

        self.log(f"Search input: {self.search_query}")
        self.log(f"Number of results: {self.number_of_results}")

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )

            self.log(f"Retrieved documents: {len(docs)}")

            data = docs_to_data(docs)
            self.log(f"Converted documents to data: {len(data)}")
            self.log(data)
            return data  # Return the search results data
        self.log("No search input provided. Skipping search.")
        return []

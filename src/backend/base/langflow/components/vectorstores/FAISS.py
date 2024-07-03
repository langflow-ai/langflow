from typing import List

from langchain_community.vectorstores import FAISS
from loguru import logger

from langflow.base.vectorstores.model import LCVectorStoreComponent
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, DataInput, HandleInput, IntInput, MultilineInput, StrInput
from langflow.schema import Data


class FaissVectorStoreComponent(LCVectorStoreComponent):
    """
    FAISS Vector Store with search capabilities
    """

    display_name: str = "FAISS"
    description: str = "FAISS Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/faiss"
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
        MultilineInput(
            name="search_query",
            display_name="Search Query",
        ),
        DataInput(
            name="ingest_data",
            display_name="Ingest Data",
            is_list=True,
        ),
        BoolInput(
            name="allow_dangerous_deserialization",
            display_name="Allow Dangerous Deserialization",
            info="Set to True to allow loading pickle files from untrusted sources. Only enable this if you trust the source of the data.",
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

    def build_vector_store(self) -> FAISS:
        """
        Builds the FAISS object.
        """
        if not self.persist_directory:
            raise ValueError("Folder path is required to save the FAISS index.")
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

    def search_documents(self) -> List[Data]:
        """
        Search for documents in the FAISS vector store.
        """
        if not self.persist_directory:
            raise ValueError("Folder path is required to load the FAISS index.")
        path = self.resolve_path(self.persist_directory)

        vector_store = FAISS.load_local(
            folder_path=path,
            embeddings=self.embedding,
            index_name=self.index_name,
            allow_dangerous_deserialization=self.allow_dangerous_deserialization,
        )

        if not vector_store:
            raise ValueError("Failed to load the FAISS index.")

        logger.debug(f"Search input: {self.search_query}")
        logger.debug(f"Number of results: {self.number_of_results}")

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )

            logger.debug(f"Retrieved documents: {len(docs)}")

            data = docs_to_data(docs)
            logger.debug(f"Converted documents to data: {len(data)}")
            logger.debug(data)
            return data  # Return the search results data
        else:
            logger.debug("No search input provided. Skipping search.")
            return []
